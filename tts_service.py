"""
OpenAI Text-to-Speech service for voice mode interactions.
Listens on port 8768 and converts text to speech using OpenAI TTS API.
"""

import socket
import json
import threading
import time
import sys
import os
import tempfile
from openai import OpenAI
from dotenv import load_dotenv

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    print("Warning: pygame not available, TTS audio playback disabled")
    PYGAME_AVAILABLE = False

try:
    from windows_toasts import WindowsToaster, Toast
    TOASTS_AVAILABLE = True
except ImportError:
    print("Warning: windows_toasts not available, notifications disabled")
    TOASTS_AVAILABLE = False

class TTSService:
    def __init__(self, port=8768):
        self.port = port
        self.running = True
        self.client = None
        self.is_playing = False  # Track if TTS is currently playing
        
        # Supported OpenAI TTS voices
        self.supported_voices = [
            # Traditional voices (confirmed working)
            'alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer',
            # New voices (added late 2024)
            'ash', 'ballad', 'coral', 'sage', 'verse'
        ]
        
        # Default voice (can be overridden by environment variable)
        self.default_voice = os.getenv('TTS_VOICE', 'onyx')
        
        # Validate default voice
        if self.default_voice not in self.supported_voices:
            print(f"[!] Warning: Default voice '{self.default_voice}' not in supported list. Using 'onyx'.")
            self.default_voice = 'onyx'
        
        print(f"[✓] TTS default voice: {self.default_voice}")
        
        # Create local temp directory for audio files
        self.temp_dir = os.path.join(os.path.dirname(__file__), 'temp_audio')
        os.makedirs(self.temp_dir, exist_ok=True)
        print(f"[✓] TTS temp directory: {self.temp_dir}")
        
        if TOASTS_AVAILABLE:
            self.toaster = WindowsToaster('TTS Service')
        else:
            self.toaster = None
        
        # Initialize OpenAI client and pygame
        self.initialize_openai()
        self.initialize_audio()
    
    def initialize_openai(self):
        """Initialize OpenAI client with API key."""
        try:
            # Load environment variables from .env file
            load_dotenv()
            
            # Get API key from environment variable
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                print("[X] OPENAI_API_KEY environment variable not found")
                print("Please set your OpenAI API key in .env file or environment variables")
                return False
            
            # Create OpenAI client
            self.client = OpenAI(api_key=api_key)
            print("[✓] OpenAI TTS client initialized successfully")
            return True
            
        except Exception as e:
            print(f"[X] Failed to initialize OpenAI TTS client: {e}")
            return False
    
    def initialize_audio(self):
        """Initialize pygame for audio playback."""
        if not PYGAME_AVAILABLE:
            print("[X] pygame not available - audio playback disabled")
            return False
        
        try:
            pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=512)
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
    
    def get_supported_voices(self):
        """Return list of supported voices."""
        return self.supported_voices.copy()
    
    def get_voice_info(self):
        """Return voice information including current default."""
        return {
            'supported_voices': self.supported_voices.copy(),
            'default_voice': self.default_voice,
            'voice_descriptions': {
                'alloy': 'Neutral, versatile voice',
                'echo': 'Articulate, precise voice',
                'fable': 'Warm, engaging voice', 
                'onyx': 'Deep, authoritative voice',
                'nova': 'Bright, energetic voice',
                'shimmer': 'Soft, gentle voice',
                'ash': 'New voice option',
                'ballad': 'New voice option',
                'coral': 'New voice option',
                'sage': 'New voice option',
                'verse': 'New voice option'
            }
        }
    
    def generate_speech(self, text, voice=None):
        """Generate speech from text using OpenAI TTS API."""
        if not self.client:
            print("[X] OpenAI client not initialized")
            return None
        
        # Use provided voice or default
        selected_voice = voice if voice else self.default_voice
        
        # Validate voice
        if selected_voice not in self.supported_voices:
            print(f"[!] Warning: Voice '{selected_voice}' not supported. Using default '{self.default_voice}'.")
            selected_voice = self.default_voice
        
        try:
            print(f"🎙️ Generating speech with voice '{selected_voice}' for: '{text[:50]}...'")
            
            response = self.client.audio.speech.create(
                model="tts-1",        # Fast model for real-time
                voice=selected_voice, # Configurable voice
                input=text,
                response_format="mp3"
            )
            
            # Create temp file in local directory
            timestamp = int(time.time() * 1000)  # millisecond precision
            temp_file = os.path.join(self.temp_dir, f"tts_{timestamp}.mp3")
            
            # Save audio to temp file
            response.stream_to_file(temp_file)
            print(f"[✓] Speech generated and saved to: {temp_file}")
            
            return temp_file
            
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
                time.sleep(0.1)
            
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
            print("[!] Aborting TTS playback...")
            self.is_playing = False
            if PYGAME_AVAILABLE:
                try:
                    pygame.mixer.music.stop()
                    # Note: unload() may not be available in all pygame versions
                    if hasattr(pygame.mixer.music, 'unload'):
                        pygame.mixer.music.unload()
                    print("[✓] TTS playback stopped")
                except Exception as e:
                    print(f"[!] Warning during TTS stop: {e}")
            return True
        else:
            print("[i] No TTS playback to abort")
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
                return {'success': success, 'message': 'TTS playback aborted' if success else 'No playback to abort'}
            
            text = request_data.get('text', '').strip()
            if not text:
                return {'success': False, 'error': 'No text provided'}
            
            # Get voice parameter (optional)
            voice = request_data.get('voice', None)
            
            print(f"📥 TTS request received: '{text[:100]}...' (voice: {voice or 'default'})")
            
            # Generate speech audio
            audio_file = self.generate_speech(text, voice)
            if not audio_file:
                return {'success': False, 'error': 'Failed to generate speech'}
            
            # Play the audio in a separate thread so abort requests can be handled
            playback_thread = threading.Thread(target=self._play_audio_threaded, args=(audio_file,))
            playback_thread.start()
            
            return {'success': True, 'message': 'Speech playback started'}
                
        except Exception as e:
            print(f"[X] Error handling TTS request: {e}")
            return {'success': False, 'error': str(e)}
    
    def handle_client(self, client_socket):
        """Handle a client connection."""
        client_addr = None
        try:
            client_addr = client_socket.getpeername()
            print(f"[i] Handling client connection from {client_addr}")
            
            # Set socket timeout to prevent hanging
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
                print(f"[i] Processing request: {request.get('action', 'tts')}")
                
                # Handle the request
                response = self.handle_tts_request(request)
                
                # Send response
                response_json = json.dumps(response) + '\n'
                client_socket.send(response_json.encode('utf-8'))
                print(f"[i] Response sent to {client_addr}")
            
        except socket.timeout:
            print(f"[!] Client connection timeout from {client_addr}")
        except json.JSONDecodeError as e:
            print(f"[X] Invalid JSON from client {client_addr}: {e}")
            error_response = json.dumps({'success': False, 'error': 'Invalid JSON'}) + '\n'
            try:
                client_socket.send(error_response.encode('utf-8'))
            except:
                pass
        except Exception as e:
            print(f"[X] Error handling client {client_addr}: {e}")
            error_response = json.dumps({'success': False, 'error': str(e)}) + '\n'
            try:
                client_socket.send(error_response.encode('utf-8'))
            except:
                pass
        
        finally:
            try:
                client_socket.close()
                print(f"[i] Closed connection to {client_addr}")
            except:
                pass
    
    def start_server(self):
        """Start the TTS server."""
        try:
            # Create socket
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('localhost', self.port))
            server_socket.listen(5)
            
            print(f"[✓] TTS service listening on localhost:{self.port}")
            self.show_toast(f"🔊 TTS Service Ready")
            
            while self.running:
                try:
                    client_socket, address = server_socket.accept()
                    # Handle each client in a separate thread
                    client_thread = threading.Thread(target=self.handle_client, args=(client_socket,))
                    client_thread.daemon = True
                    client_thread.start()
                    
                except socket.error:
                    if self.running:
                        print("[!] Socket error occurred")
                    break
            
        except Exception as e:
            print(f"[X] TTS service error: {e}")
            self.show_toast(f"❌ TTS Service Error: {e}")
        
        finally:
            try:
                server_socket.close()
            except:
                pass
    
    def stop(self):
        """Stop the TTS service."""
        print("[!] Stopping TTS service...")
        self.running = False
        
        # Clean up any remaining temp files
        try:
            if os.path.exists(self.temp_dir):
                for file in os.listdir(self.temp_dir):
                    if file.startswith('tts_') and file.endswith('.mp3'):
                        file_path = os.path.join(self.temp_dir, file)
                        self.cleanup_temp_file(file_path)
        except Exception as e:
            print(f"[!] Error during cleanup: {e}")

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    print("\n[!] TTS service shutdown requested")
    if 'service' in globals():
        service.stop()
    sys.exit(0)

def main():
    """Main function to start the TTS service."""
    global service
    
    print("=" * 60)
    print("🔊 OpenAI Text-to-Speech Service Starting...")
    print("=" * 60)
    
    # Create and start the service
    service = TTSService()
    
    # Set up signal handlers for graceful shutdown
    import signal
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        service.start_server()
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)
    except Exception as e:
        print(f"[X] TTS service crashed: {e}")
        service.show_toast(f"❌ TTS service crashed: {e}")

if __name__ == "__main__":
    main()