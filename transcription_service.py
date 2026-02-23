"""
Background transcription service that keeps Whisper model loaded in GPU.
Listens for transcription requests and returns results via socket communication.
"""

import os
import sys
import socket
import json
import threading
import tempfile
import numpy as np
from scipy.io.wavfile import write
from faster_whisper import WhisperModel
import time
import signal
import ahocorasick
try:
    from windows_toasts import WindowsToaster, Toast
    TOASTS_AVAILABLE = True
except ImportError:
    TOASTS_AVAILABLE = False

class TranscriptionService:
    def __init__(self, port=8765):
        self.port = port
        self.model = None
        self.device_used = None
        self.model_size = "turbo"
        self.running = True
        if TOASTS_AVAILABLE:
            self.toaster = WindowsToaster('Voice Transcription')
        else:
            self.toaster = None

        # Initialize corrections
        self.corrections_automaton = None
        self._build_corrections_automaton()

        # Use the same models folder as your main app
        self.models_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")

    def load_model(self):
        """Load Whisper model with GPU acceleration."""
        try:
            # Set environment variable to avoid symlink issues
            os.environ['HF_HUB_DISABLE_SYMLINKS'] = '1'

            # Try GPU first, fall back to CPU
            try:
                self.model = WhisperModel(
                    self.model_size,
                    device="cuda",
                    compute_type="float16",  # Optimized for Tensor cores
                    num_workers=1,  # Optimal for single GPU operations
                    cpu_threads=8,  # Optimized thread allocation for GPU workloads
                    device_index=0,  # Explicit GPU binding for faster startup
                    download_root=self.models_path
                )
                self.device_used = "GPU"

                # Warm up CUDA kernels for faster first transcription
                self._warmup_cuda_kernels()
                self.show_toast("🎯 GPU turbo transcription ready!")

            except Exception:
                # Fallback to CPU
                self.model = WhisperModel(
                    self.model_size,
                    device="cpu",
                    compute_type="int8",
                    num_workers=1,
                    cpu_threads=8,
                    download_root=self.models_path
                )
                self.device_used = "CPU"
                self.show_toast("✅ CPU turbo transcription ready!")

        except Exception as e:
            error_msg = f"❌ Failed to load model: {e}"
            self.show_toast(error_msg)
            raise RuntimeError(error_msg)

    def _warmup_cuda_kernels(self):
        """Warm up CUDA kernels with a dummy transcription for faster first run."""
        try:
            if self.device_used == "GPU":
                # Create a short dummy audio file (1 second of silence)
                dummy_audio = np.zeros(16000, dtype=np.float32)  # 1 second at 16kHz

                # Use local warmup file to avoid IT policy temp directory issues
                warmup_file = os.path.join(os.path.dirname(__file__), "warmup_audio.wav")

                try:
                    # Convert to int16 and save to local directory
                    audio_int16 = np.int16(dummy_audio * 32767)
                    write(warmup_file, 16000, audio_int16)

                    # Run a quick transcription to warm up kernels
                    segments, _ = self.model.transcribe(
                        warmup_file,
                        beam_size=1,
                        vad_filter=False,  # Skip VAD for warmup
                        word_timestamps=False,
                        condition_on_previous_text=False,
                        temperature=0.0
                    )

                    # Consume the generator to ensure kernels are compiled
                    list(segments)

                finally:
                    # Clean up warmup file
                    try:
                        if os.path.exists(warmup_file):
                            os.remove(warmup_file)
                    except:
                        pass  # Non-critical cleanup

        except Exception:
            pass  # Non-critical warmup failure

    def show_toast(self, message):
        """Show Windows toast notification."""
        if not TOASTS_AVAILABLE or not self.toaster:
            return
        try:
            toast = Toast()
            toast.text_fields = [message]
            self.toaster.show_toast(toast)
        except Exception:
            pass

    def transcribe_audio_data(self, audio_data, sample_rate=16000):
        """Transcribe audio data using the loaded model."""
        if self.model is None:
            return None, "Model not loaded"

        tmp_filename = None
        try:
            # Save audio to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                # Convert float32 to int16 for WAV file
                audio_int16 = np.int16(audio_data * 32767)
                write(tmp_file.name, sample_rate, audio_int16)
                tmp_filename = tmp_file.name

            # Transcribe with Whisper
            segments, info = self.model.transcribe(
                tmp_filename,
                language="en",  # English language hint for better accuracy
                beam_size=5,  # Default quality setting - better punctuation and grammar
                vad_filter=True,  # Keep VAD for better segmentation with defaults
                word_timestamps=False,  # Skip unnecessary computation
                without_timestamps=False,  # Enable timestamps for better sentence boundaries
                condition_on_previous_text=True,  # Enable context for better punctuation and flow
                compression_ratio_threshold=2.4,  # Skip bad segments faster
                log_prob_threshold=-1.0,  # Reduce false positives
                temperature=[0.0, 0.2, 0.4],  # Fallback for difficult audio
                initial_prompt="Transcribe with proper punctuation, capitalization, and sentence structure."
            )

            # Combine all segments
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())

            text = " ".join(text_parts).strip()

            # === START SMART CORRECTIONS FEATURE ===
            # To disable: Set ENABLE_CORRECTIONS = False or comment out this entire block
            ENABLE_CORRECTIONS = True

            if ENABLE_CORRECTIONS and text:
                try:
                    text = self.apply_smart_corrections(text)
                except Exception:
                    pass  # Fail silently - don't break transcription if corrections fail
            # === END SMART CORRECTIONS FEATURE ===

            if text:
                return text, None
            else:
                return None, "No speech detected"

        except Exception as e:
            error_msg = f"Transcription failed: {e}"

            # Try CPU fallback if GPU failed
            if self.device_used == "GPU":
                try:
                    self.model = WhisperModel(
                        self.model_size,
                        device="cpu",
                        compute_type="int8",
                        num_workers=1,
                        cpu_threads=8,
                        download_root=self.models_path
                    )
                    self.device_used = "CPU"
                    return self.transcribe_audio_data(audio_data, sample_rate)
                except Exception as cpu_error:
                    return None, f"Both GPU and CPU transcription failed: {cpu_error}"

            return None, error_msg

        finally:
            # Clean up temporary file
            if tmp_filename and os.path.exists(tmp_filename):
                try:
                    os.remove(tmp_filename)
                except:
                    pass

    # === START SMART CORRECTIONS METHODS ===
    # These methods handle auto-corrections for common transcription errors
    # To disable: Set ENABLE_CORRECTIONS = False in transcribe_audio_data method

    def _build_corrections_automaton(self):
        """Build Aho-Corasick automaton for corrections."""
        corrections_file = os.path.join(os.path.dirname(__file__), "corrections.txt")

        if not os.path.exists(corrections_file):
            self.corrections_automaton = None
            return

        corrections = {}

        try:
            with open(corrections_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue

                    if ':' in line:
                        wrong, right = line.split(':', 1)
                        wrong = wrong.strip().lower()
                        right = right.strip()
                        corrections[wrong] = right

            # Build automaton
            self.corrections_automaton = ahocorasick.Automaton()
            for pattern, replacement in corrections.items():
                self.corrections_automaton.add_word(pattern, replacement)
            self.corrections_automaton.make_automaton()

        except Exception:
            self.corrections_automaton = None

    def apply_smart_corrections(self, text):
        """Apply smart corrections using Aho-Corasick algorithm."""
        if not self.corrections_automaton:
            return text

        matches = []
        text_lower = text.lower()

        for end_idx, replacement in self.corrections_automaton.iter(text_lower):
            # Find the pattern that matched
            for pattern in self.corrections_automaton:
                pattern_len = len(pattern)
                if (end_idx >= pattern_len - 1 and
                    text_lower[end_idx - pattern_len + 1:end_idx + 1] == pattern):
                    start_idx = end_idx - pattern_len + 1
                    matches.append((start_idx, end_idx + 1, replacement))
                    break

        if not matches:
            return text

        # Sort by position (reverse order to preserve indices)
        matches.sort(reverse=True)

        # Apply replacements
        result = text
        for start, end, replacement in matches:
            result = result[:start] + replacement + result[end:]

        return result

    # === END SMART CORRECTIONS METHODS ===

    def handle_client(self, client_socket):
        """Handle a client transcription request."""
        try:
            # Receive request data
            data = b""
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                data += chunk

                # Check if we have the complete message
                try:
                    if data.endswith(b'\n'):
                        request = json.loads(data.decode('utf-8').strip())
                        break
                except:
                    continue

            if not data:
                return

            # Process the request
            if request['action'] == 'transcribe':
                audio_array = np.array(request['audio_data'], dtype=np.float32)
                sample_rate = request['sample_rate']

                # Transcribe the audio
                text, error = self.transcribe_audio_data(audio_array, sample_rate)

                # Send response
                response = {
                    'success': text is not None,
                    'text': text,
                    'error': error
                }

                response_json = json.dumps(response) + '\n'
                client_socket.send(response_json.encode('utf-8'))

        except Exception as e:
            try:
                error_response = json.dumps({'success': False, 'error': str(e)}) + '\n'
                client_socket.send(error_response.encode('utf-8'))
            except:
                pass
        finally:
            client_socket.close()

    def start_server(self):
        """Start the transcription service server."""
        # Load the model first
        self.load_model()

        # Create server socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            server_socket.bind(('localhost', self.port))
            server_socket.listen(5)
            server_socket.settimeout(1.0)  # Non-blocking accept

            while self.running:
                try:
                    client_socket, addr = server_socket.accept()

                    # Handle client in a separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket,)
                    )
                    client_thread.daemon = True
                    client_thread.start()

                except socket.timeout:
                    continue  # Check if we should keep running
                except Exception:
                    if self.running:
                        pass

        except Exception as e:
            self.show_toast(f"❌ Service failed to start: {e}")
        finally:
            server_socket.close()

    def stop(self):
        """Stop the service."""
        self.running = False
        self.show_toast("🛑 Voice transcription service stopped")


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    service.stop()
    sys.exit(0)

if __name__ == "__main__":
    # Set up signal handling for clean shutdown
    service = TranscriptionService()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        service.start_server()
    except KeyboardInterrupt:
        service.stop()
    except Exception:
        pass
