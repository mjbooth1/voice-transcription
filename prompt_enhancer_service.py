"""
Background prompt enhancement service using OpenAI GPT-4.
Listens for enhancement requests and returns improved prompts via socket communication.
"""

import os
import sys
import socket
import json
import threading
import time
import signal
from openai import OpenAI
from dotenv import load_dotenv

try:
    from windows_toasts import WindowsToaster, Toast
    TOASTS_AVAILABLE = True
except ImportError:
    print("Warning: windows_toasts not available, notifications disabled")
    TOASTS_AVAILABLE = False

class PromptEnhancementService:
    def __init__(self, port=8766):
        self.port = port
        self.client = None
        self.running = True
        
        if TOASTS_AVAILABLE:
            self.toaster = WindowsToaster('Prompt Enhancement')
        else:
            self.toaster = None
        
        # Load environment variables from .env file
        load_dotenv()
        
        # Command prompt registry
        self.command_prompts = {
            'enhance': """You are translating a transcription from a user into a command for an AI agent. Focus on objectives and tasks. Order them in logical order. Make them simple and concise.""",
            
            'summarize': """Summarize the following text concisely. Capture key points and main ideas. Be brief but comprehensive.""",
            
            'slack': """Rewrite this message to sound natural and casual for Slack. Use a friendly, conversational tone. Keep it concise and engaging.""",
            
            'email': """Convert this into a professional, well-formatted email. Use clear subject matter, concise sentences, and bullet points where appropriate. Structure: greeting, main content, action items (if any), closing."""
        }
        
    def load_openai_client(self):
        """Initialize OpenAI client with API key."""
        try:
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                error_msg = "❌ OPENAI_API_KEY not found in environment variables"
                print(error_msg)
                self.show_toast(error_msg)
                raise ValueError(error_msg)
            
            self.show_toast("🔄 Loading GPT-4o enhancement service...")
            print("Initializing OpenAI client with GPT-4o...")
            
            self.client = OpenAI(api_key=api_key)
            
            # Test the connection with a simple request
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "Test connection. Reply with 'OK'."}],
                max_tokens=5,
                temperature=0
            )
            
            if response.choices[0].message.content.strip() == "OK":
                print("🎯 GPT-4o connection successful")
                self.show_toast("🎯 GPT-4o prompt enhancer ready!")
            else:
                raise Exception("GPT-4o test response unexpected")
                
        except Exception as e:
            error_msg = f"❌ Failed to initialize GPT-4o: {e}"
            print(error_msg)
            self.show_toast(error_msg)
            raise RuntimeError(error_msg)
    
    def show_toast(self, message):
        """Show Windows toast notification."""
        print(f"📢 {message}")  # Always print to console
        if not TOASTS_AVAILABLE or not self.toaster:
            return
        try:
            toast = Toast()
            toast.text_fields = [message]
            self.toaster.show_toast(toast)
        except Exception as e:
            print(f"Toast notification failed: {e}")
    
    def process_command(self, text, command_type='enhance'):
        """Process text using GPT-4o with specified command type."""
        if self.client is None:
            return None, "GPT-4 client not initialized"
        
        if not text or not text.strip():
            return None, f"No text provided for {command_type}"
        
        if command_type not in self.command_prompts:
            return None, f"Unknown command type: {command_type}"
        
        try:
            print(f"🔄 Processing {command_type} command with GPT-4o...")
            print(f"📝 Original text: '{text[:100]}...'")
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": self.command_prompts[command_type]},
                    {"role": "user", "content": text}
                ],
                max_tokens=500,
                temperature=0.3,
                top_p=1.0
            )
            
            enhanced_text = response.choices[0].message.content.strip()
            
            if enhanced_text:
                print(f"✅ {command_type.title()} complete: '{enhanced_text[:100]}...'")
                return enhanced_text, None
            else:
                return None, f"GPT-4o returned empty response for {command_type}"
                
        except Exception as e:
            error_msg = f"{command_type.title()} failed: {e}"
            print(f"❌ {error_msg}")
            return None, error_msg
    
    def handle_client(self, client_socket):
        """Handle a client enhancement request."""
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
            
            # Process the request - support multiple command types
            if request['action'] in ['enhance', 'summarize', 'slack', 'email']:
                original_text = request['text']
                command_type = request['action']
                
                # Process the text with GPT-4o using specified command
                processed_text, error = self.process_command(original_text, command_type)
                
                # Send response
                response = {
                    'success': processed_text is not None,
                    'processed_text': processed_text,
                    'original_text': original_text,
                    'command_type': command_type,
                    'error': error
                }
                
                response_json = json.dumps(response) + '\n'
                client_socket.send(response_json.encode('utf-8'))
            
        except Exception as e:
            print(f"Error handling client: {e}")
            try:
                error_response = json.dumps({'success': False, 'error': str(e)}) + '\n'
                client_socket.send(error_response.encode('utf-8'))
            except:
                pass
        finally:
            client_socket.close()
    
    def start_server(self):
        """Start the prompt enhancement service server."""
        # Load GPT-4 client first
        self.load_openai_client()
        
        # Create server socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            server_socket.bind(('localhost', self.port))
            server_socket.listen(5)
            server_socket.settimeout(1.0)  # Non-blocking accept
            
            print(f"🚀 Prompt enhancement service running on localhost:{self.port}")
            print(f"🤖 Using GPT-4o for prompt enhancement")
            print("✨ Ready for prompt enhancement commands!")
            
            while self.running:
                try:
                    client_socket, addr = server_socket.accept()
                    print(f"📞 Enhancement client connected from {addr}")
                    
                    # Handle client in a separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket,)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except socket.timeout:
                    continue  # Check if we should keep running
                except Exception as e:
                    if self.running:
                        print(f"Server error: {e}")
                        
        except Exception as e:
            print(f"❌ Failed to start enhancement server: {e}")
            self.show_toast(f"❌ Enhancement service failed to start: {e}")
        finally:
            server_socket.close()
            print("🔴 Prompt enhancement service stopped")
            
    def stop(self):
        """Stop the service."""
        self.running = False
        print("🛑 Stopping prompt enhancement service...")
        self.show_toast("🛑 Prompt enhancement service stopped")

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    print("🔴 Received shutdown signal")
    service.stop()
    sys.exit(0)

if __name__ == "__main__":
    # Set up signal handling for clean shutdown
    service = PromptEnhancementService()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        service.start_server()
    except KeyboardInterrupt:
        service.stop()
    except Exception as e:
        print(f"❌ Enhancement service crashed: {e}")
        service.show_toast(f"❌ Enhancement service crashed: {e}")