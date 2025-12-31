"""
Local TTS service using Piper for ultra-fast text-to-speech.
Runs alongside OpenAI TTS service - can switch between them via config.
"""

import socket
import json
import threading
import time
import sys
import os
import wave
from pathlib import Path
from dotenv import load_dotenv

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    print("Warning: pygame not available, audio playback disabled")
    PYGAME_AVAILABLE = False

try:
    from windows_toasts import WindowsToaster, Toast
    TOASTS_AVAILABLE = True
except ImportError:
    print("Warning: windows_toasts not available, notifications disabled")
    TOASTS_AVAILABLE = False

try:
    from piper.voice import PiperVoice
    PIPER_AVAILABLE = True
except ImportError:
    print("Warning: piper-tts not available, install with: pip install piper-tts")
    PIPER_AVAILABLE = False

class LocalTTSService:
    def __init__(self, port=8769):
        self.port = port
        self.running = True
        self.is_playing = False
        self.voice_model = None
        
        # Check if piper module is available
        if not PIPER_AVAILABLE:
            print("[X] piper-tts module not available, please install: pip install piper-tts")
            sys.exit(1)
        
        # Load environment variables
        load_dotenv()
        
        # Voice configuration
        self.voice = os.getenv('PIPER_VOICE', 'lessac')
        print(f"[✓] Selected voice: {self.voice}")
        
        # Find model path
        self.model_dir = Path(__file__).parent.parent / "models" / "piper"
        self.model_path = None
        self.config_path = None
        
        self._find_model_files()
        
        # Load the Piper voice model
        self._load_voice_model()
        
        # Create local temp directory for audio files
        self.temp_dir = os.path.join(os.path.dirname(__file__), 'temp_audio_local')
        os.makedirs(self.temp_dir, exist_ok=True)
        print(f"[✓] Local TTS temp directory: {self.temp_dir}")
        
        if TOASTS_AVAILABLE:
            self.toaster = WindowsToaster('Local TTS Service')
        else:
            self.toaster = None
        
        # Initialize audio system
        self.initialize_audio()
        
        # Test Piper installation
        self.test_piper()
        
    def _find_model_files(self):
        """Find the model and config files for the selected voice."""
        # Try different quality levels for the selected voice
        voice_patterns = [
            f"en_US-{self.voice}-high",
            f"en_US-{self.voice}-medium", 
            f"en_US-{self.voice}-low"
        ]
        
        for pattern in voice_patterns:
            model_file = self.model_dir / f"{pattern}.onnx"
            config_file = self.model_dir / f"{pattern}.onnx.json"
            
            if model_file.exists() and config_file.exists():
                self.model_path = str(model_file)
                self.config_path = str(config_file)
                print(f"[✓] Found model: {model_file.name}")
                return
        
        print(f"[X] No model found for voice '{self.voice}' in {self.model_dir}")
        print(f"Available models: {list(self.model_dir.glob('*.onnx'))}")
        sys.exit(1)
    
    def _load_voice_model(self):
        """Load the Piper voice model using Python module."""
        try:
            print(f"[i] Loading Piper voice model: {Path(self.model_path).name}")
            self.voice_model = PiperVoice.load(self.model_path, self.config_path)
            print(f"[✓] Piper voice model loaded successfully")
            print(f"[i] Sample rate: {self.voice_model.config.sample_rate}Hz")
        except Exception as e:
            print(f"[X] Failed to load Piper voice model: {e}")
            sys.exit(1)
    
    def test_piper(self):
        """Test that Piper TTS is working."""
        try:
            # Test with a simple phrase using the loaded model
            test_text = "Testing Piper TTS."
            print(f"[i] Testing Piper voice synthesis...")
            
            # Create a temporary test file
            test_file = os.path.join(self.temp_dir, "test_piper.wav")
            
            # Generate test audio
            with open(test_file, 'wb') as f:
                with wave.Wave_write(f) as wav:
                    wav.setnchannels(1)  # Mono audio
                    wav.setsampwidth(2)  # 16-bit audio
                    wav.setframerate(self.voice_model.config.sample_rate)
                    self.voice_model.synthesize(test_text, wav)
            
            # Check if file was created and has content
            if os.path.exists(test_file) and os.path.getsize(test_file) > 1000:
                print("[✓] Piper TTS test successful")
                # Clean up test file
                os.remove(test_file)
                return True
            else:
                print("[X] Piper test failed: no audio generated")
                return False
                
        except Exception as e:
            print(f"[X] Piper test error: {e}")
            return False
    
    def initialize_audio(self):
        """Initialize pygame for audio playback."""
        if not PYGAME_AVAILABLE:
            print("[X] pygame not available - audio playback disabled")
            return False
        
        try:
            pygame.mixer.pre_init(frequency=22050, size=-16, channels=1, buffer=512)
            pygame.mixer.init()
            print("[✓] pygame audio system initialized")
            return True
        except Exception as e:
            print(f"[X] Failed to initialize pygame audio: {e}")
            return False
    
    def show_toast(self, message):
        """Show Windows toast notification."""
        print(f"🔊 {message}")
        if self.toaster:
            try:
                toast = Toast()
                toast.text_fields = [message]
                self.toaster.show_toast(toast)
            except Exception as e:
                print(f"Toast notification failed: {e}")
    
    def generate_speech(self, text, voice=None):
        """Generate speech from text using Piper TTS Python module."""
        try:
            print(f"🎙️ Generating speech with Piper ({self.voice}): '{text[:50]}...'")
            
            # Create temp file for audio output
            timestamp = int(time.time() * 1000)
            temp_file = os.path.join(self.temp_dir, f"piper_{timestamp}.wav")
            
            # Use Piper Python module to generate speech
            with open(temp_file, 'wb') as f:
                with wave.Wave_write(f) as wav:
                    wav.setnchannels(1)  # Mono audio
                    wav.setsampwidth(2)  # 16-bit audio  
                    wav.setframerate(self.voice_model.config.sample_rate)
                    self.voice_model.synthesize(text, wav)
            
            if os.path.exists(temp_file) and os.path.getsize(temp_file) > 100:
                print(f"[✓] Speech generated: {temp_file}")
                return temp_file
            else:
                print(f"[X] Piper generation failed: no audio output")
                return None
                
        except Exception as e:
            print(f"[X] Failed to generate speech: {e}")
            return None
    
    def play_audio(self, filepath):
        """Play audio file using pygame with abort capability."""
        if not PYGAME_AVAILABLE:
            print("[X] Cannot play audio - pygame not available")
            return False
        
        try:
            print(f"🔊 Playing audio: {filepath}")
            self.is_playing = True
            
            # Load and play the audio file
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            
            # Wait for playback to complete, checking for abort
            while pygame.mixer.music.get_busy() and self.is_playing:
                time.sleep(0.05)  # Check every 50ms for faster abort response
            
            if not self.is_playing:
                # TTS was aborted
                pygame.mixer.music.stop()
                print("[!] Audio playback aborted by user")
                return False
            else:
                print("[✓] Audio playback completed")
                return True
            
        except Exception as e:
            print(f"[X] Failed to play audio: {e}")
            return False
        finally:
            self.is_playing = False
    
    def _play_audio_threaded(self, filepath):
        """Play audio in a separate thread and clean up afterward."""
        try:
            playback_success = self.play_audio(filepath)
            print(f"[✓] Audio playback {'completed' if playback_success else 'aborted/failed'}")
        finally:
            # Always clean up temp file
            self.cleanup_temp_file(filepath)
    
    def abort_playback(self):
        """Abort current TTS playback."""
        was_playing = self.is_playing
        if was_playing:
            print("[!] Aborting local TTS playback...")
            self.is_playing = False
            if PYGAME_AVAILABLE:
                try:
                    pygame.mixer.music.stop()
                    print("[✓] Local TTS playback stopped")
                except Exception as e:
                    print(f"[!] Warning during TTS stop: {e}")
            return True
        else:
            print("[i] No local TTS playback to abort")
            return False
    
    def cleanup_temp_file(self, filepath):
        """Remove temporary audio file."""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"[✓] Cleaned up temp file: {filepath}")
        except Exception as e:
            print(f"[!] Failed to cleanup temp file {filepath}: {e}")
    
    def handle_tts_request(self, request_data):
        """Handle incoming TTS request."""
        try:
            # Check for abort request
            if request_data.get('action') == 'abort':
                success = self.abort_playback()
                return {'success': success, 'message': 'Local TTS playback aborted' if success else 'No playback to abort'}
            
            text = request_data.get('text', '').strip()
            if not text:
                return {'success': False, 'error': 'No text provided'}
            
            # Voice parameter is ignored for Piper (uses configured voice)
            voice = request_data.get('voice', None)
            if voice:
                print(f"[i] Voice parameter '{voice}' ignored (using configured voice '{self.voice}')")
            
            print(f"📥 Local TTS request: '{text[:100]}...'")
            
            # Generate speech audio
            audio_file = self.generate_speech(text)
            if not audio_file:
                return {'success': False, 'error': 'Failed to generate speech'}
            
            # Play the audio in a separate thread so abort requests can be handled
            playback_thread = threading.Thread(target=self._play_audio_threaded, args=(audio_file,))
            playback_thread.start()
            
            return {'success': True, 'message': 'Local speech playback started'}
                
        except Exception as e:
            print(f"[X] Error handling local TTS request: {e}")
            return {'success': False, 'error': str(e)}
    
    def handle_client(self, client_socket):
        """Handle a client connection."""
        client_addr = None
        try:
            client_addr = client_socket.getpeername()
            print(f"[i] Local TTS handling client: {client_addr}")
            
            # Set socket timeout
            client_socket.settimeout(30)
            
            # Receive request data
            request_data = b""
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                request_data += chunk
                if request_data.endswith(b'\n'):
                    break
            
            if request_data:
                # Parse JSON request
                request = json.loads(request_data.decode('utf-8').strip())
                print(f"[i] Local TTS processing: {request.get('action', 'tts')}")
                
                # Handle the request
                response = self.handle_tts_request(request)
                
                # Send response
                response_json = json.dumps(response) + '\n'
                client_socket.send(response_json.encode('utf-8'))
                print(f"[i] Response sent to {client_addr}")
            
        except socket.timeout:
            print(f"[!] Local TTS client timeout: {client_addr}")
        except json.JSONDecodeError as e:
            print(f"[X] Invalid JSON from local TTS client {client_addr}: {e}")
            error_response = json.dumps({'success': False, 'error': 'Invalid JSON'}) + '\n'
            try:
                client_socket.send(error_response.encode('utf-8'))
            except:
                pass
        except Exception as e:
            print(f"[X] Error handling local TTS client {client_addr}: {e}")
            error_response = json.dumps({'success': False, 'error': str(e)}) + '\n'
            try:
                client_socket.send(error_response.encode('utf-8'))
            except:
                pass
        
        finally:
            try:
                client_socket.close()
                print(f"[i] Closed local TTS connection to {client_addr}")
            except:
                pass
    
    def start_server(self):
        """Start the local TTS server."""
        try:
            # Create socket
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('localhost', self.port))
            server_socket.listen(5)
            
            print(f"[✓] Local TTS service listening on localhost:{self.port}")
            print(f"[✓] Using voice: {self.voice}")
            self.show_toast(f"🔊 Local TTS Ready ({self.voice})")
            
            while self.running:
                try:
                    client_socket, address = server_socket.accept()
                    # Handle each client in a separate thread
                    client_thread = threading.Thread(target=self.handle_client, args=(client_socket,))
                    client_thread.daemon = True
                    client_thread.start()
                    
                except socket.error:
                    if self.running:
                        print("[!] Socket error in local TTS")
                    break
            
        except Exception as e:
            print(f"[X] Local TTS service error: {e}")
            self.show_toast(f"❌ Local TTS Error: {e}")
        
        finally:
            try:
                server_socket.close()
            except:
                pass
    
    def stop(self):
        """Stop the local TTS service."""
        print("[!] Stopping local TTS service...")
        self.running = False
        
        # Clean up any remaining temp files
        try:
            if os.path.exists(self.temp_dir):
                for file in os.listdir(self.temp_dir):
                    if file.startswith('piper_') and file.endswith('.wav'):
                        file_path = os.path.join(self.temp_dir, file)
                        self.cleanup_temp_file(file_path)
        except Exception as e:
            print(f"[!] Error during local TTS cleanup: {e}")

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    print("\n[!] Local TTS service shutdown requested")
    if 'service' in globals():
        service.stop()
    sys.exit(0)

def main():
    """Main function to start the local TTS service."""
    global service
    
    print("=" * 60)
    print("🔊 Local Piper TTS Service Starting...")
    print("=" * 60)
    
    # Create and start the service
    service = LocalTTSService()
    
    # Set up signal handlers for graceful shutdown
    import signal
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        service.start_server()
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)
    except Exception as e:
        print(f"[X] Local TTS service crashed: {e}")
        service.show_toast(f"❌ Local TTS crashed: {e}")

if __name__ == "__main__":
    main()