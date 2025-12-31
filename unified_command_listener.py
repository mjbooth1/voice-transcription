"""
Unified global hotkey listener for all GPT-4o commands.
Handles multiple hotkeys for different AI commands.
"""

import socket
import json
import threading
import time
import sys
import pyperclip
from pynput import keyboard
from pynput.keyboard import Key, GlobalHotKeys
import signal

try:
    from windows_toasts import WindowsToaster, Toast
    TOASTS_AVAILABLE = True
except ImportError:
    print("Warning: windows_toasts not available, notifications disabled")
    TOASTS_AVAILABLE = False

class UnifiedCommandListener:
    def __init__(self, server_port=8766):
        self.server_port = server_port
        self.running = True
        
        if TOASTS_AVAILABLE:
            self.toaster = WindowsToaster('AI Commands')
        else:
            self.toaster = None
        
        self.keyboard_controller = keyboard.Controller()
        self.hotkey_listener = None
        self.currently_processing = False
        self.toast_queue = []
        self.execution_counter = 0
        self.hotkey_trigger_count = 0
        
        # Command mappings
        self.commands = {
            'enhance': {
                'hotkey': '<ctrl>+<alt>+e',
                'display_name': 'AI Enhancement',
                'toast_processing': '🤖 Enhancing with GPT-4o...',
                'toast_success': '✅ Enhanced!'
            },
            'summarize': {
                'hotkey': '<ctrl>+<alt>+w',
                'display_name': 'Summarize',
                'toast_processing': '📝 Summarizing with GPT-4o...',
                'toast_success': '✅ Summarized!'
            },
            'slack': {
                'hotkey': '<ctrl>+<alt>+s',
                'display_name': 'Slack Rewrite',
                'toast_processing': '💬 Rewriting for Slack...',
                'toast_success': '✅ Slack ready!'
            },
            'email': {
                'hotkey': '<ctrl>+<alt>+m',
                'display_name': 'Email Format',
                'toast_processing': '📧 Converting to email...',
                'toast_success': '✅ Email formatted!'
            }
        }
    
    def show_toast(self, message, duration=None):
        """Show Windows toast notification - thread-safe version."""
        print(f"📢 {message}")  # Always print to console
        if not TOASTS_AVAILABLE or not self.toaster:
            return
        
        # Queue toast for main thread to display
        self.toast_queue.append((message, duration))
    
    def show_brief_toast(self, message):
        """Show a brief toast that disappears quickly."""
        self.show_toast(message, duration="short")
    
    def _process_toast_queue(self):
        """Process queued toasts from main thread."""
        while self.toast_queue:
            message, duration = self.toast_queue.pop(0)
            try:
                toast = Toast()
                toast.text_fields = [message]
                if duration == "short":
                    toast.duration = "short"
                self.toaster.show_toast(toast)
            except Exception as e:
                print(f"Toast notification failed: {e}")
    
    def is_service_running(self):
        """Check if the command processing service is running."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('localhost', self.server_port))
            sock.close()
            return result == 0
        except:
            return False
    
    def wait_for_service(self):
        """Wait for the command processing service to start."""
        print("🔍 Waiting for command processing service to start...")
        while self.running and not self.is_service_running():
            time.sleep(1)
        
        if self.running:
            print("✅ Command processing service detected!")
            # Build hotkey ready message
            hotkey_list = []
            for cmd_type, cmd_info in self.commands.items():
                hotkey = cmd_info['hotkey'].replace('<', '').replace('>', '').replace('+', '+').title()
                hotkey_list.append(f"{hotkey} ({cmd_info['display_name']})")
            
            ready_msg = f"🎯 AI Commands Ready: {', '.join(hotkey_list)}"
            self.show_toast(ready_msg)
    
    def get_clipboard_text(self):
        """Get text from clipboard."""
        try:
            text = pyperclip.paste()
            if text and text.strip():
                return text.strip()
            else:
                return None
        except Exception as e:
            print(f"❌ Failed to read clipboard: {e}")
            return None
    
    def set_clipboard_and_paste(self, text):
        """Set clipboard content and paste at cursor."""
        try:
            # Copy processed text to clipboard
            pyperclip.copy(text)
            
            # Small delay to ensure clipboard is updated
            time.sleep(0.1)
            
            # Paste using Ctrl+V
            self.keyboard_controller.press(Key.ctrl)
            self.keyboard_controller.press('v')
            self.keyboard_controller.release('v')
            self.keyboard_controller.release(Key.ctrl)
            
            print(f"✅ Pasted processed text: '{text[:50]}...'")
            
        except Exception as e:
            print(f"❌ Failed to paste processed text: {e}")
            self.show_toast(f"❌ Failed to paste: {e}")
    
    def send_command_request(self, text, command_type):
        """Send text to command processing service and get result."""
        try:
            # Connect to service
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)  # 30 second timeout for GPT-4o response
            sock.connect(('localhost', self.server_port))
            
            # Prepare request
            request = {
                'action': command_type,
                'text': text
            }
            
            # Send request
            request_json = json.dumps(request) + '\n'
            sock.send(request_json.encode('utf-8'))
            
            # Receive response
            response_data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response_data += chunk
                if response_data.endswith(b'\n'):
                    break
            
            sock.close()
            
            if not response_data:
                return None, "No response from command processing service"
            
            response = json.loads(response_data.decode('utf-8').strip())
            
            if response['success']:
                return response['processed_text'], None
            else:
                return None, response['error']
                
        except Exception as e:
            return None, f"Communication error: {e}"
    
    def handle_command_trigger(self, command_type, trigger_id):
        """Handle a command hotkey trigger - get clipboard, process, and paste."""
        self.execution_counter += 1
        exec_id = self.execution_counter
        
        start_time = time.time()
        cmd_info = self.commands[command_type]
        print(f"✨ HANDLE_COMMAND_TRIGGER: {cmd_info['display_name']} execution #{exec_id} for trigger #{trigger_id} at {start_time:.3f}")
        
        # Check if service is running
        if not self.is_service_running():
            self.show_toast(f"❌ Command processing service not running")
            return
        
        # Get text from clipboard
        clipboard_text = self.get_clipboard_text()
        if not clipboard_text:
            self.show_toast(f"❌ No text found in clipboard for {cmd_info['display_name']}")
            return
        
        print(f"📋 Original text from clipboard: '{clipboard_text[:50]}...'")
        
        # Show processing toast
        self.show_brief_toast(cmd_info['toast_processing'])
        
        # Send for processing
        processed_text, error = self.send_command_request(clipboard_text, command_type)
        
        if processed_text:
            print(f"✅ {cmd_info['display_name']} processed: '{processed_text[:50]}...'")
            # Auto-paste the processed text
            self.set_clipboard_and_paste(processed_text)
            self.show_brief_toast(cmd_info['toast_success'])
        else:
            error_msg = f"❌ {cmd_info['display_name']} failed: {error}"
            print(error_msg)
            self.show_toast(error_msg)
    
    def create_hotkey_handler(self, command_type):
        """Create a hotkey handler for specific command type."""
        def handler():
            self.hotkey_trigger_count += 1
            trigger_id = self.hotkey_trigger_count
            
            cmd_info = self.commands[command_type]
            print(f"🔥 {cmd_info['display_name'].upper()} HOTKEY TRIGGERED #{trigger_id} at {time.time():.3f}")
            print(f"🔥 Currently processing: {self.currently_processing}")
            
            # Prevent duplicate execution
            if self.currently_processing:
                print(f"⚠️ BLOCKED: Already processing, ignoring {cmd_info['display_name']} trigger #{trigger_id}")
                return
                
            print(f"✨ STARTING: {cmd_info['display_name']} hotkey #{trigger_id}")
            self.currently_processing = True
            
            # Trigger processing in a separate thread to avoid blocking
            thread = threading.Thread(target=self._handle_command_with_cleanup, args=(command_type, trigger_id), daemon=True)
            thread.start()
            print(f"🧵 {cmd_info['display_name'].upper()} THREAD CREATED: {thread.name} for trigger #{trigger_id}")
        
        return handler
    
    def _handle_command_with_cleanup(self, command_type, trigger_id):
        """Wrapper to handle command with proper cleanup."""
        cmd_info = self.commands[command_type]
        print(f"🧵 {cmd_info['display_name'].upper()} THREAD STARTED: Processing trigger #{trigger_id}")
        try:
            self.handle_command_trigger(command_type, trigger_id)
        finally:
            print(f"🧵 {cmd_info['display_name'].upper()} THREAD CLEANUP: Finished trigger #{trigger_id}, setting currently_processing = False")
            self.currently_processing = False
    
    def start_listening(self):
        """Start the global command hotkey listeners."""
        print("🚀 Starting unified AI command hotkey listeners...")
        
        # Display all hotkeys
        for cmd_type, cmd_info in self.commands.items():
            hotkey_display = cmd_info['hotkey'].replace('<', '').replace('>', '').replace('+', '+').title()
            print(f"✨ {hotkey_display} → {cmd_info['display_name']}")
        
        print("🛑 Press Ctrl+C to stop listeners")
        
        # Wait for service to be ready
        self.wait_for_service()
        
        if not self.running:
            return
        
        # Build hotkey mappings
        try:
            hotkey_mappings = {}
            for cmd_type, cmd_info in self.commands.items():
                hotkey_mappings[cmd_info['hotkey']] = self.create_hotkey_handler(cmd_type)
            
            print("🔧 Registering global hotkeys...")
            with GlobalHotKeys(hotkey_mappings) as hotkey_listener:
                self.hotkey_listener = hotkey_listener
                print("✅ All global hotkeys registered successfully")
                
                while self.running:
                    # Process any queued toasts from main thread
                    self._process_toast_queue()
                    time.sleep(0.1)
                    
        except Exception as e:
            print(f"❌ Global hotkey listeners error: {e}")
            self.show_toast(f"❌ Hotkey listeners error: {e}")
    
    def stop(self):
        """Stop all hotkey listeners."""
        self.running = False
        print("🔴 Stopping all AI command hotkey listeners...")
        self.show_toast("🔴 AI command listeners stopped")

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    print("🔴 Received shutdown signal")
    listener.stop()
    sys.exit(0)

if __name__ == "__main__":
    # Set up signal handling for clean shutdown
    listener = UnifiedCommandListener()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        listener.start_listening()
    except KeyboardInterrupt:
        listener.stop()
    except Exception as e:
        print(f"❌ Unified command listener crashed: {e}")
        listener.show_toast(f"❌ Command listener crashed: {e}")