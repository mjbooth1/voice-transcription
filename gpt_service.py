"""
Simple GPT-4o API service for voice transcription commands.
Listens on port 8767 and processes prompts using OpenAI's GPT-4o.
"""

import socket
import json
import threading
import time
import sys
import os
from openai import OpenAI
from dotenv import load_dotenv

# Console output will use ASCII characters for Windows compatibility

try:
    from windows_toasts import WindowsToaster, Toast
    TOASTS_AVAILABLE = True
except ImportError:
    print("Warning: windows_toasts not available, notifications disabled")
    TOASTS_AVAILABLE = False

class GPTService:
    def __init__(self, port=8767):
        self.port = port
        self.running = True
        self.client = None
        
        if TOASTS_AVAILABLE:
            self.toaster = WindowsToaster('GPT Service')
        else:
            self.toaster = None
        
        # Initialize OpenAI client
        self.initialize_openai()
    
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
            
            self.client = OpenAI(api_key=api_key)
            print("[OK] OpenAI client initialized successfully")
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to initialize OpenAI client: {e}")
            return False
    
    def show_toast(self, message):
        """Show Windows toast notification."""
        print(f"[INFO] {message}")
        if not TOASTS_AVAILABLE or not self.toaster:
            return
        
        try:
            toast = Toast()
            toast.text_fields = [message]
            self.toaster.show_toast(toast)
        except Exception as e:
            print(f"Toast notification failed: {e}")
    
    def process_gpt_request(self, prompt):
        """Send prompt to GPT-4o and get response."""
        if not self.client:
            return None, "OpenAI client not initialized"
        
        try:
            print(f"[GPT] Sending prompt to GPT-4o: '{prompt[:100]}...'")
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a helpful assistant. Provide clear, concise responses to user requests."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            result = response.choices[0].message.content.strip()
            print(f"[OK] GPT-4o response: '{result[:100]}...'")
            return result, None
            
        except Exception as e:
            error_msg = f"GPT-4o request failed: {e}"
            print(f"[ERROR] {error_msg}")
            return None, error_msg
    
    def handle_client(self, client_socket, addr):
        """Handle individual client request."""
        try:
            print(f"[CLIENT] Connected from {addr}")
            
            # Receive request
            request_data = b""
            while True:
                chunk = client_socket.recv(1024)
                if not chunk:
                    break
                request_data += chunk
                if request_data.endswith(b'\n'):
                    break
            
            if not request_data:
                return
            
            # Parse request
            try:
                request = json.loads(request_data.decode('utf-8').strip())
            except json.JSONDecodeError as e:
                print(f"[ERROR] Invalid JSON received: {e}")
                return
            
            action = request.get('action')
            
            if action == 'gpt_query':
                prompt = request.get('prompt', '')
                if not prompt:
                    response = {'success': False, 'error': 'No prompt provided'}
                else:
                    # Process with GPT-4o
                    gpt_response, error = self.process_gpt_request(prompt)
                    
                    if gpt_response:
                        response = {'success': True, 'response': gpt_response}
                    else:
                        response = {'success': False, 'error': error or 'Unknown error'}
            else:
                response = {'success': False, 'error': f'Unknown action: {action}'}
            
            # Send response
            response_json = json.dumps(response) + '\n'
            client_socket.send(response_json.encode('utf-8'))
            
            print(f"[OK] Response sent to {addr}")
            
        except Exception as e:
            print(f"[ERROR] Error handling client {addr}: {e}")
        finally:
            client_socket.close()
    
    def start_server(self):
        """Start the GPT service server."""
        if not self.client:
            print("[ERROR] Cannot start server - OpenAI client not initialized")
            return
        
        try:
            # Create socket
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('localhost', self.port))
            server_socket.listen(5)
            
            print(f"[START] GPT Service started on port {self.port}")
            print("[READY] Ready to process GPT-4o requests")
            self.show_toast("✨ GPT Service Ready")
            
            while self.running:
                try:
                    # Accept client connection
                    client_socket, addr = server_socket.accept()
                    
                    # Handle client in separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client, 
                        args=(client_socket, addr),
                        daemon=True
                    )
                    client_thread.start()
                    
                except Exception as e:
                    if self.running:  # Only log if we're still supposed to be running
                        print(f"[ERROR] Error accepting client: {e}")
            
        except Exception as e:
            print(f"[ERROR] Server error: {e}")
        finally:
            try:
                server_socket.close()
            except:
                pass
            print("[STOP] GPT Service stopped")
    
    def stop(self):
        """Stop the GPT service."""
        self.running = False
        print("[STOP] Stopping GPT service...")

def main():
    """Main entry point."""
    service = GPTService()
    
    try:
        service.start_server()
    except KeyboardInterrupt:
        service.stop()
    except Exception as e:
        print(f"[CRASH] GPT Service crashed: {e}")

if __name__ == "__main__":
    main()