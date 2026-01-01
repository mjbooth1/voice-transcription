"""
Persistent global hotkey listener for instant voice transcription.
Runs continuously, listening for Ctrl+Alt+A to trigger recording.
"""

import socket
import json
import numpy as np
import sounddevice as sd
import threading
import time
import sys
import os
import pyperclip
from pynput import keyboard, mouse
from pynput.keyboard import Key, Listener as KeyboardListener, GlobalHotKeys
from pynput.mouse import Button, Listener as MouseListener
import signal

# Windows API for checking modifier keys
try:
    from ctypes import windll
    user32 = windll.user32
    VK_CONTROL = 0x11
    VK_SHIFT = 0x10
    GetKeyState = user32.GetKeyState
    GetAsyncKeyState = user32.GetAsyncKeyState
except ImportError:
    print("Warning: Could not import Windows API for key detection")
    GetKeyState = None
    GetAsyncKeyState = None
    VK_CONTROL = VK_SHIFT = 0

try:
    from windows_toasts import WindowsToaster, Toast
    TOASTS_AVAILABLE = True
except ImportError:
    print("Warning: windows_toasts not available, notifications disabled")
    TOASTS_AVAILABLE = False

class GlobalHotkeyListener:
    def __init__(self, server_port=8765, hotkey_combo=None):
        self.server_port = server_port
        self.recording = False
        self.audio_buffer = []
        self.sample_rate = 16000
        self.running = True

        if TOASTS_AVAILABLE:
            self.toaster = WindowsToaster('Voice Transcription')
        else:
            self.toaster = None

        self.keyboard_controller = keyboard.Controller()

        # Use proper global hotkey registration (doesn't interfere with typing)
        self.hotkey_listener = None
        self.mouse_listener = None

        # Pre-initialize audio system for instant response
        self.audio_stream = None
        self.service_socket = None
        self.is_initialized = False

        # Threading controls
        self.currently_recording = False
        self.toast_queue = []

        # Recording mode tracking
        self.recording_mode = "normal"  # normal, gpt_direct, gpt_clipboard

        # Global keyboard listener for MetaLeft detection
        self.kbd_listener = None

        # Pre-import everything that might be needed during recording
        self._preload_imports()

        # Reference to self for win32 event filter
        self.listener_instance = None

        # Voice buffer for GPT commands
        self.last_transcription = ""
        
    
    def _preload_imports(self):
        """Pre-import all modules that will be needed during recording."""
        try:
            # Force import of all modules we'll need
            import json
            import socket
            import numpy as np
            import sounddevice as sd
            import pyperclip
            from pynput.keyboard import Key, Listener as KeyboardListener
            from pynput import keyboard
            print("✅ All imports pre-loaded")
        except Exception as e:
            print(f"⚠️ Some imports failed to preload: {e}")
        
    def win32_event_filter(self, msg, data):
        """Windows-specific event filter to handle XButton events and suppress navigation."""
        # WM_XBUTTONDOWN = 523 (button press)
        if msg == 523:  # Only handle button down events
            # Extract which button from HIWORD of wParam
            # data.mouseData HIWORD contains XBUTTON1 (1) or XBUTTON2 (2)
            xbutton = (data.mouseData >> 16) & 0xFFFF
            
            if xbutton == 1:  # XBUTTON1 = Back button - STOP recording
                if self.currently_recording:
                    # Currently recording - stop recording
                    print("🔴 Back button: Stopping recording")
                    self.recording = False

                # Suppress the navigation event
                if self.listener_instance:
                    self.listener_instance.suppress_event()
                return False  # Hide from other callbacks
                
            elif xbutton == 2:  # XBUTTON2 = Forward button - START recording
                # Check for modifier keys to determine recording mode
                # Use GetAsyncKeyState for real-time key state (check high bit 0x8000)
                ctrl_pressed = (GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0 if GetAsyncKeyState else False
                shift_pressed = (GetAsyncKeyState(VK_SHIFT) & 0x8000) != 0 if GetAsyncKeyState else False

                print(f"🔍 DEBUG: Forward button - Ctrl: {ctrl_pressed}, Shift: {shift_pressed}")

                if ctrl_pressed:
                    self.recording_mode = "gpt_direct"
                    print(f"🖱️ Ctrl+Forward pressed - GPT Direct mode")
                elif shift_pressed:
                    self.recording_mode = "gpt_clipboard"
                    print(f"🖱️ Shift+Forward pressed - GPT with Clipboard mode")
                else:
                    self.recording_mode = "normal"
                    print(f"🖱️ Forward pressed - Normal mode (transcribe and type)")
                
                # Trigger recording start
                self._trigger_recording(f"mouse_forward_x2_{self.recording_mode}")
                # Suppress the navigation event
                if self.listener_instance:
                    self.listener_instance.suppress_event()
                return False  # Hide from other callbacks
        
        # WM_XBUTTONUP = 524 - suppress but don't handle
        elif msg == 524:  # Button release
            xbutton = (data.mouseData >> 16) & 0xFFFF
            if xbutton in [1, 2]:  # Either XButton
                # Just suppress the release event, don't trigger any action
                if self.listener_instance:
                    self.listener_instance.suppress_event()
                return False  # Hide from other callbacks
        
        # Middle button events are no longer used - removed for cleaner operation
        
        # Allow all other events
        return True
    
    def win32_keyboard_filter(self, msg, data):
        """Keyboard filter - REMOVED to fix Task View issues."""
        # Let all keyboard events through normally - no filtering
        return True
    
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
                self.toaster.show_toast(toast)
            except Exception as e:
                print(f"Toast notification failed: {e}")
    
    def is_service_running(self):
        """Check if the transcription service is running."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('localhost', self.server_port))
            sock.close()
            return result == 0
        except:
            return False
    
    def wait_for_service(self):
        """Wait for the transcription service to start."""
        print("🔍 Waiting for transcription service to start...")
        while self.running and not self.is_service_running():
            time.sleep(1)
        
        if self.running:
            print("✅ Transcription service detected!")
            # Pre-initialize audio system for instant response
            self.pre_initialize_audio()
            if self.is_initialized:
                self.show_toast("🎯 Voice Ready (Forward/Ctrl+Forward/Shift+Forward)")
            else:
                self.show_toast("⚠️ Voice ready (audio init failed)")
    
    def pre_initialize_audio(self):
        """Pre-initialize audio system for instant recording response."""
        try:
            print("🔧 Pre-initializing audio system...")
            
            # Test audio devices are available
            devices = sd.query_devices()
            print(f"📻 Found {len(devices)} audio devices")
            
            # Pre-configure audio settings
            sd.check_input_settings(
                device=None,
                channels=1,
                samplerate=self.sample_rate,
                dtype='float32'
            )
            
            # Test a quick audio stream to ensure everything works
            def test_callback(indata, frames, time, status):
                pass  # Do nothing, just test the stream works
            
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                callback=test_callback,
                dtype='float32',
                blocksize=int(self.sample_rate * 0.1)  # 100ms chunks
            ) as test_stream:
                # Let it run briefly to ensure audio system is ready
                time.sleep(0.1)
            
            # Pre-test service connection and keep it warm
            if self.is_service_running():
                print("✅ Service connection verified")
                # Pre-warm the service connection
                self._warm_service_connection()
            
            print("✅ Audio system pre-initialized successfully")
            self.is_initialized = True
            
        except Exception as e:
            print(f"⚠️ Audio pre-initialization failed: {e}")
            self.is_initialized = False
    
    def _warm_service_connection(self):
        """Pre-warm the service connection to reduce first-request latency."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            sock.connect(('localhost', self.server_port))
            sock.close()
            print("✅ Service connection warmed")
        except Exception as e:
            print(f"⚠️ Service connection warm-up failed: {e}")
    
    def record_audio_fast(self):
        """Record audio until ESC is pressed - optimized for instant start."""
        method_start = time.time()
        # Fast recording started
        
        service_check_start = time.time()
        if not self.is_service_running():
            self.show_toast("❌ Transcription service not running")
            return None
        print(f"⏱️ Service check took {time.time() - service_check_start:.3f}s")
        
        buffer_start = time.time()
        self.audio_buffer = []
        self.recording = True
        print(f"⏱️ Buffer setup took {time.time() - buffer_start:.3f}s")
        
        def audio_callback(indata, frames, time_info, status):
            if status:
                print(f"Audio status: {status}")
            if self.recording:
                self.audio_buffer.append(indata[:, 0].copy())  # Mono channel
        
        # Set up listeners for stop recording (ESC key or XButton1)
        def on_key_press_recording(key):
            if key == Key.esc:
                print("⌨️ ESC PRESSED: stopping recording and transcribing")
                self.recording = False
                return False  # Stop listener
        
        def on_mouse_click_recording(x, y, button, pressed):
            if not pressed:  # Only handle press events
                return
            # Button.x1 (back button - bottom side) for stop recording
            if button == Button.x1:
                # Back button pressed - stopping recording
                self.recording = False
                return False  # Stop listener
        
        listener_start = time.time()
        keyboard_listener = KeyboardListener(on_press=on_key_press_recording)
        mouse_listener_recording = MouseListener(on_click=on_mouse_click_recording)
        keyboard_listener.start()
        mouse_listener_recording.start()
        # Listeners initialized
        
        try:
            stream_start = time.time()
            # Use pre-configured audio settings for instant start
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                callback=audio_callback,
                dtype='float32',
                blocksize=int(self.sample_rate * 0.1)  # Pre-configured chunk size
            ):
                print(f"⏱️ Audio stream creation took {time.time() - stream_start:.3f}s")
                
                toast_start = time.time()
                # Show initial recording toast
                self.show_toast("🎤 Recording... (Press ESC to transcribe)")
                print(f"⏱️ Toast display took {time.time() - toast_start:.3f}s")
                print("🎤 RECORDING STARTED: Press ESC to stop and transcribe")
                
                start_time = time.time()
                
                while self.recording:
                    elapsed = time.time() - start_time
                    
                    if elapsed > 180:  # Max 3 minutes
                        print("Maximum recording time reached (3 minutes)")
                        self.show_brief_toast("⏰ 3 minute recording limit reached")
                        break
                    time.sleep(0.1)
                
                print("🎤 Recording stopped")
                
        except Exception as e:
            print(f"Recording error: {e}")
            self.show_toast(f"❌ Recording error: {e}")
            return None
        
        finally:
            keyboard_listener.stop()
            mouse_listener_recording.stop()
        
        if not self.audio_buffer:
            return None
        
        # Combine audio chunks
        audio_data = np.concatenate(self.audio_buffer)
        duration = len(audio_data) / self.sample_rate
        print(f"Recorded {duration:.2f} seconds of audio")
        
        # Show transcription notification for longer recordings or GPT modes
        if self.recording_mode in ["gpt_direct", "gpt_clipboard"]:
            self.show_brief_toast("✨ Transcribing and sending to GPT...")
        elif duration > 15:
            self.show_brief_toast("🔄 Transcribing...")
        
        return audio_data
    
    def send_transcription_request(self, audio_data):
        """Send audio to transcription service and get result."""
        try:
            # Connect to service
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)  # 30 second timeout for transcription
            sock.connect(('localhost', self.server_port))
            
            # Prepare request
            request = {
                'action': 'transcribe',
                'audio_data': audio_data.tolist(),
                'sample_rate': self.sample_rate
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
                return None, "No response from service"
            
            response = json.loads(response_data.decode('utf-8').strip())
            
            if response['success']:
                return response['text'], None
            else:
                return None, response['error']
                
        except Exception as e:
            return None, f"Communication error: {e}"
    
    def normalize_gpt_response(self, text):
        """Normalize GPT response text to remove excessive formatting and indentation."""
        import re
        
        # Split into lines for processing
        lines = text.split('\n')
        normalized_lines = []
        
        for line in lines:
            # Remove leading/trailing whitespace
            line = line.strip()
            
            # Skip empty lines (preserve paragraph breaks)
            if not line:
                normalized_lines.append('')
                continue
            
            # Remove markdown bullet points and excessive indentation
            # Match patterns like "- ", "* ", "• ", "  - ", "    * ", etc.
            line = re.sub(r'^[\s]*[-*•]\s+', '- ', line)
            
            # Convert multiple levels of indentation to simpler format
            # Replace 4+ spaces or tabs with 2 spaces for sub-items
            if re.match(r'^\s{4,}', line):
                line = re.sub(r'^\s{4,}', '  ', line)
            elif re.match(r'^\t+', line):
                line = re.sub(r'^\t+', '  ', line)
            
            normalized_lines.append(line)
        
        # Join lines back together, removing excessive blank lines
        result = '\n'.join(normalized_lines)
        
        # Remove multiple consecutive newlines (keep max 2 for paragraph breaks)
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        return result.strip()

    def paste_via_clipboard(self, text):
        """Paste text via clipboard (Ctrl+V) instead of typing character-by-character.

        This prevents React-based terminal UIs (like Claude Code CLI) from hitting
        maximum update depth errors caused by rapid individual character inputs.
        """
        try:
            # Save current clipboard content
            original_clipboard = pyperclip.paste()
        except:
            original_clipboard = None

        try:
            # Copy text to clipboard and paste immediately
            pyperclip.copy(text)
            with self.keyboard_controller.pressed(Key.ctrl):
                self.keyboard_controller.tap('v')

        finally:
            # Restore original clipboard after paste completes
            if original_clipboard is not None:
                time.sleep(0.05)  # Brief wait for paste to complete before restoring
                pyperclip.copy(original_clipboard)

    def paste_text(self, text):
        """Handle text output based on recording mode."""
        try:
            # Store in voice buffer
            self.last_transcription = text

            if self.recording_mode == "normal":
                # Normal mode - paste transcription via clipboard (prevents React update loops)
                self.paste_via_clipboard(text)
                print(f"✅ Normal mode - Pasted: '{text[:50]}...'")

            elif self.recording_mode == "gpt_direct":
                # GPT direct mode - send only transcription to GPT
                print(f"🤖 GPT Direct mode - Sending: '{text[:50]}...'")
                response = self.send_to_gpt(text)
                if response:
                    normalized_response = self.normalize_gpt_response(response)
                    self.paste_via_clipboard(normalized_response)
                    print(f"✅ GPT response: '{response[:50]}...'")
                else:
                    self.show_toast("❌ GPT request failed")

            elif self.recording_mode == "gpt_clipboard":
                # GPT with clipboard mode - combine with clipboard and send to GPT
                try:
                    clipboard = pyperclip.paste().strip() if pyperclip.paste() else ""
                except:
                    clipboard = ""

                if clipboard:
                    combined = f"{text}\n\n{clipboard}"
                    print(f"🤖 GPT Clipboard mode - Combined: '{combined[:100]}...'")
                else:
                    combined = text
                    print(f"🤖 GPT Clipboard mode (empty clipboard) - Text only: '{text[:50]}...'")

                # Toast already shown during transcription for longer recordings
                response = self.send_to_gpt(combined)
                if response:
                    normalized_response = self.normalize_gpt_response(response)
                    self.paste_via_clipboard(normalized_response)
                    print(f"✅ GPT response: '{response[:50]}...'")
                else:
                    self.show_toast("❌ GPT request failed")

            # Reset to normal mode after processing
            self.recording_mode = "normal"
            
        except Exception as e:
            print(f"❌ Failed to handle text: {e}")
            self.show_toast(f"❌ Failed to process: {e}")
            self.recording_mode = "normal"  # Reset on error
    
    def handle_hotkey_trigger(self):
        """Handle the hotkey trigger - record and transcribe with optimized speed."""
        
        start_time = time.time()
        # Processing hotkey trigger
        
        # Use fast recording if audio system is pre-initialized
        before_record = time.time()
        print(f"⏱️ Starting recording at {before_record:.3f} (delay: {before_record - start_time:.3f}s)")
        
        if self.is_initialized:
            # Using fast recording
            audio_data = self.record_audio_fast()
        else:
            # Using standard recording
            audio_data = self.record_audio()
            
        if audio_data is None:
            print("❌ No audio recorded")
            return
        
        # No need for "Transcribing..." toast - it's already shown briefly by ESC handler
        
        # Send for transcription
        text, error = self.send_transcription_request(audio_data)
        
        if text:
            # Auto-paste the transcribed text
            self.paste_text(text)
        else:
            error_msg = f"❌ Transcription failed: {error}"
            print(error_msg)
            self.show_toast(error_msg)
    
    def on_hotkey_triggered(self):
        """Called when Ctrl+Alt+A is pressed."""
        self._trigger_recording("keyboard")
    
    def on_global_key_press(self, key):
        """Handle global keyboard events - backup for keys not caught by win32_keyboard_filter."""
        # The win32_keyboard_filter should handle Windows key suppression
        # This is kept as a fallback for other potential keyboard events
        pass
    
    def on_mouse_button_pressed(self, x, y, button, pressed):
        """Called when mouse buttons are pressed (XButtons handled by win32_event_filter)."""
        if not pressed:  # Only handle press events, not release
            return
            
        # XButton events (x1, x2) are handled by win32_event_filter
        # This callback handles other mouse buttons if needed
        if button not in [Button.x1, Button.x2]:
            # Other mouse button pressed
            # Handle other buttons if needed in the future
            pass
    
    def _trigger_recording(self, source):
        """Common method to trigger recording from keyboard or mouse."""
        
        # Recording trigger activated
        
        # Prevent duplicate execution
        if self.currently_recording:
            # Already recording - ignoring trigger
            return
            
        # Starting transcription
        self.currently_recording = True
        
        # Trigger transcription in a separate thread to avoid blocking
        thread = threading.Thread(target=self._handle_hotkey_with_cleanup, daemon=True)
        thread.start()
        # Transcription thread started
    
    def _handle_hotkey_with_cleanup(self):
        """Wrapper to handle hotkey with proper cleanup."""
        # Processing trigger
        try:
            self.handle_hotkey_trigger()
        finally:
            # Finished processing trigger
            self.currently_recording = False

    def send_to_gpt(self, prompt):
        """Send prompt to GPT-4o service and get response."""
        print(f"🔍 DEBUG: Attempting to send prompt to GPT service (length: {len(prompt)})")
        print(f"🔍 DEBUG: Prompt preview: '{prompt[:100]}...'")
        try:
            # Connect to GPT service (port 8767 to avoid conflicts)
            print(f"🔍 DEBUG: Connecting to localhost:8767...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)  # 30 second timeout for GPT response
            sock.connect(('localhost', 8767))
            print(f"✅ DEBUG: Connected to GPT service successfully")
            
            # Prepare request
            request = {
                'action': 'gpt_query',
                'prompt': prompt
            }
            
            # Send request
            request_json = json.dumps(request) + '\n'
            print(f"🔍 DEBUG: Sending request: {request_json[:200]}...")
            sock.send(request_json.encode('utf-8'))
            print(f"🔍 DEBUG: Request sent, waiting for response...")
            
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
                print(f"❌ DEBUG: No response data received from GPT service")
                return None
            
            print(f"🔍 DEBUG: Received response: {response_data[:200]}...")
            response = json.loads(response_data.decode('utf-8').strip())
            print(f"🔍 DEBUG: Parsed response: {response}")
            
            if response.get('success'):
                print(f"✅ DEBUG: GPT success, response length: {len(response['response'])}")
                return response['response']
            else:
                error_msg = response.get('error', 'Unknown error')
                print(f"❌ DEBUG: GPT service error: {error_msg}")
                return None
                
        except Exception as e:
            print(f"❌ DEBUG: GPT communication error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def start_listening(self):
        """Start the global hotkey listener."""
        print("🚀 Starting voice transcription system...")
        print("🎯 Forward button - Normal recording (types at cursor)")
        print("🤖 Ctrl+Forward button - GPT direct (transcription only)")
        print("📋 Shift+Forward button - GPT with clipboard (transcription + clipboard)")
        print("⏹️ Back button or Escape - Stop recording")
        print("🛑 Press Ctrl+C to stop listener")
        
        # Wait for service to be ready
        self.wait_for_service()
        
        if not self.running:
            return
        
        # Use proper GlobalHotKeys that don't interfere with normal typing
        try:
            hotkeys = {
                '<ctrl>+<alt>+a': self.on_hotkey_triggered
            }
            
            print("🔧 Registering global hotkey Ctrl+Alt+A and mouse listener with XButton suppression...")
            
            # Start mouse listener for global mouse buttons with suppression
            self.mouse_listener = MouseListener(
                on_click=self.on_mouse_button_pressed,
                win32_event_filter=self.win32_event_filter,
                suppress=False  # Use selective suppression via filter
            )
            self.listener_instance = self.mouse_listener  # Store reference for filter
            self.mouse_listener.start()
            
            # Keyboard listener removed - was causing Task View issues
            # self.kbd_listener = None
            
            with GlobalHotKeys(hotkeys) as hotkey_listener:
                self.hotkey_listener = hotkey_listener
                print("✅ Global hotkey and mouse listeners registered successfully")
                
                while self.running:
                    # Process any queued toasts from main thread
                    self._process_toast_queue()
                    time.sleep(0.1)
                    
        except Exception as e:
            print(f"❌ Global hotkey listener error: {e}")
            self.show_toast(f"❌ Hotkey listener error: {e}")
    
    def stop(self):
        """Stop the hotkey and mouse listeners."""
        self.running = False
        print("🔴 Stopping hotkey and mouse listeners...")
        if self.mouse_listener:
            self.mouse_listener.stop()
        # Keyboard listener removed to fix Task View issues
        self.show_toast("🔴 Voice hotkey listener stopped")

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    print("🔴 Received shutdown signal")
    listener.stop()
    sys.exit(0)

if __name__ == "__main__":
    # Set up signal handling for clean shutdown
    listener = GlobalHotkeyListener()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        listener.start_listening()
    except KeyboardInterrupt:
        listener.stop()
    except Exception as e:
        print(f"❌ Hotkey listener crashed: {e}")
        listener.show_toast(f"❌ Hotkey listener crashed: {e}")