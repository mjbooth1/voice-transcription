"""
Simple GPT API service for voice transcription commands.
Listens on port 8767 and processes prompts using OpenAI GPT.
Model configured via GPT_MODEL in .env (default: gpt-6-sol).
"""

import socket
import json
import threading
import sys
import os
from openai import OpenAI
from dotenv import load_dotenv
from academic_scientific import load_academic_scientific_prompt

GENERAL_SYSTEM_PROMPT = "You are a helpful assistant. Provide clear, concise responses to user requests."

# Legacy toast backend intentionally disabled. User-visible status now belongs
# exclusively to the microphone icon in hotkey_listener.py.
# try:
#     from windows_toasts import WindowsToaster, Toast
#     TOASTS_AVAILABLE = True
# except ImportError:
#     TOASTS_AVAILABLE = False

class GPTService:
    def __init__(self, port=8767):
        self.port = port
        self.running = True
        self.client = None

        # Legacy toast initialization intentionally disabled.
        # if TOASTS_AVAILABLE:
        #     self.toaster = WindowsToaster('GPT Service')
        # else:
        #     self.toaster = None

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
                return False

            # Get model settings from environment variables.
            self.model = os.getenv('GPT_MODEL', 'gpt-6-sol')
            self.reasoning_effort = os.getenv('GPT_REASONING_EFFORT', 'none')
            self.max_output_tokens = int(os.getenv('GPT_MAX_OUTPUT_TOKENS', '2000'))

            self.client = OpenAI(api_key=api_key)
            return True

        except Exception:
            return False

    # Legacy toast method intentionally disabled and retained for reference.
    # def show_toast(self, message):
    #     if not TOASTS_AVAILABLE or not self.toaster:
    #         return
    #     toast = Toast()
    #     toast.text_fields = [message]
    #     self.toaster.show_toast(toast)

    def process_gpt_request(self, prompt, mode="general"):
        """Send prompt to GPT and get response."""
        if not self.client:
            return None, "OpenAI client not initialized"

        try:
            system_prompt = (
                load_academic_scientific_prompt()
                if mode == "academic_scientific"
                else GENERAL_SYSTEM_PROMPT
            )
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_completion_tokens=self.max_output_tokens,
                reasoning_effort=self.reasoning_effort
            )

            result = response.choices[0].message.content.strip()
            return result, None

        except Exception as e:
            error_msg = f"GPT request failed: {e}"
            return None, error_msg

    def handle_client(self, client_socket, addr):
        """Handle individual client request."""
        try:
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
            except json.JSONDecodeError:
                return

            action = request.get('action')

            if action == 'gpt_query':
                prompt = request.get('prompt', '')
                mode = request.get('mode', 'general')
                if not prompt:
                    response = {'success': False, 'error': 'No prompt provided'}
                else:
                    # Process with GPT
                    gpt_response, error = self.process_gpt_request(prompt, mode=mode)

                    if gpt_response:
                        response = {'success': True, 'response': gpt_response}
                    else:
                        response = {'success': False, 'error': error or 'Unknown error'}
            else:
                response = {'success': False, 'error': f'Unknown action: {action}'}

            # Send response
            response_json = json.dumps(response) + '\n'
            client_socket.send(response_json.encode('utf-8'))

        except Exception:
            pass
        finally:
            client_socket.close()

    def start_server(self):
        """Start the GPT service server."""
        if not self.client:
            return

        try:
            # Create socket
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('localhost', self.port))
            server_socket.listen(5)

            # Legacy ready toast disabled; the tray listener probes this port.

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

                except Exception:
                    pass

        except Exception:
            pass
        finally:
            try:
                server_socket.close()
            except:
                pass

    def stop(self):
        """Stop the GPT service."""
        self.running = False


def main():
    """Main entry point."""
    service = GPTService()

    try:
        service.start_server()
    except KeyboardInterrupt:
        service.stop()
    except Exception:
        pass

if __name__ == "__main__":
    main()
