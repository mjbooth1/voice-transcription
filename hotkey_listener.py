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
from tray_indicator import TrayIndicator, TrayState

# Windows API for checking modifier keys
try:
    from ctypes import windll
    user32 = windll.user32
    VK_CONTROL = 0x11
    VK_SHIFT = 0x10
    GetKeyState = user32.GetKeyState
    GetAsyncKeyState = user32.GetAsyncKeyState
    GetDoubleClickTime = user32.GetDoubleClickTime
except (ImportError, AttributeError):
    GetKeyState = None
    GetAsyncKeyState = None
    GetDoubleClickTime = None
    VK_CONTROL = VK_SHIFT = 0

# Legacy toast backend intentionally disabled in favor of the persistent tray icon.
# Kept here as a migration reference only; this code must not be executable.
# try:
#     from windows_toasts import WindowsToaster, Toast
#     TOASTS_AVAILABLE = True
# except ImportError:
#     TOASTS_AVAILABLE = False


def get_double_forward_window_seconds():
    """Return the Windows double-click interval, capped at 500 ms."""
    try:
        interval_ms = int(GetDoubleClickTime()) if GetDoubleClickTime else 500
    except Exception:
        interval_ms = 500

    if interval_ms <= 0:
        interval_ms = 500

    return min(interval_ms, 500) / 1000.0


class GlobalHotkeyListener:
    def __init__(self, server_port=8765, hotkey_combo=None, tray_indicator=None):
        self.server_port = server_port
        self.recording = False
        self.audio_buffer = []
        self.sample_rate = 16000
        self.running = True

        self.tray = tray_indicator or TrayIndicator()
        self.health_error = None
        self.workflow_error = None
        self.initialization_error = None
        self.instance_lock_socket = None

        # Legacy toast initialization intentionally disabled.
        # if TOASTS_AVAILABLE:
        #     self.toaster = WindowsToaster('Voice Transcription')
        # else:
        #     self.toaster = None

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
        self.state_lock = threading.Lock()

        # Recording mode tracking
        self.recording_mode = "normal"  # normal, gpt_direct, gpt_clipboard, academic_scientific
        self.last_unmodified_forward_at = None
        self.double_forward_window_seconds = get_double_forward_window_seconds()

        # Reference to self for win32 event filter
        self.listener_instance = None

        # Voice buffer for GPT commands
        self.last_transcription = ""

    def win32_event_filter(self, msg, data):
        """Windows-specific event filter to handle XButton events and suppress navigation."""
        # WM_XBUTTONDOWN = 523 (button press)
        if msg == 523:  # Only handle button down events
            # Extract which button from HIWORD of wParam
            # data.mouseData HIWORD contains XBUTTON1 (1) or XBUTTON2 (2)
            xbutton = (data.mouseData >> 16) & 0xFFFF

            if xbutton == 1:  # XBUTTON1 = Back button - STOP recording
                self._stop_recording()

                # Suppress the navigation event
                if self.listener_instance:
                    self.listener_instance.suppress_event()
                return False  # Hide from other callbacks

            elif xbutton == 2:  # XBUTTON2 = Forward button - START recording
                # Check for modifier keys to determine recording mode
                # Use GetAsyncKeyState for real-time key state (check high bit 0x8000)
                ctrl_pressed = (GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0 if GetAsyncKeyState else False
                shift_pressed = (GetAsyncKeyState(VK_SHIFT) & 0x8000) != 0 if GetAsyncKeyState else False

                self._handle_forward_press(ctrl_pressed, shift_pressed)
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

        # Allow all other events
        return True

    def _handle_forward_press(self, ctrl_pressed=False, shift_pressed=False, pressed_at=None):
        """Start a mouse mode or promote a rapid unmodified pair to academic mode."""
        pressed_at = time.monotonic() if pressed_at is None else pressed_at
        should_start = False
        recognized_academic = False
        source = "mouse_forward_normal"

        with self.state_lock:
            if ctrl_pressed or shift_pressed:
                self.last_unmodified_forward_at = None
                if self.currently_recording:
                    return "ignored"

                self.recording_mode = "gpt_direct" if ctrl_pressed else "gpt_clipboard"
                source = f"mouse_forward_{self.recording_mode}"
                should_start = True
            elif not self.currently_recording:
                self.recording_mode = "normal"
                self.last_unmodified_forward_at = pressed_at
                should_start = True
            else:
                first_press = self.last_unmodified_forward_at
                self.last_unmodified_forward_at = None
                if (
                    self.recording_mode == "normal"
                    and first_press is not None
                    and 0 <= pressed_at - first_press <= self.double_forward_window_seconds
                ):
                    self.recording_mode = "academic_scientific"
                    recognized_academic = True

        if recognized_academic:
            return "academic_scientific"

        if should_start:
            self._trigger_recording(source)
            return "started"

        return "ignored"

    def _stop_recording(self):
        """Stop the active capture and invalidate any pending double-forward gesture."""
        should_show_stopping = False
        with self.state_lock:
            self.last_unmodified_forward_at = None
            if self.currently_recording and self.recording:
                self.recording = False
                should_show_stopping = True

        if should_show_stopping:
            self._set_tray_state(TrayState.STOPPING)

    # Legacy toast methods intentionally disabled. Tray state and error methods
    # below are the only active user-feedback path.
    # def show_toast(self, message, duration=None):
    #     if not TOASTS_AVAILABLE or not self.toaster:
    #         return
    #     self.toast_queue.append((message, duration))
    #
    # def show_brief_toast(self, message):
    #     self.show_toast(message, duration="short")
    #
    # def _process_toast_queue(self):
    #     while self.toast_queue:
    #         message, duration = self.toast_queue.pop(0)
    #         toast = Toast()
    #         toast.text_fields = [message]
    #         self.toaster.show_toast(toast)

    def _set_tray_state(self, state, detail=None):
        tray = getattr(self, "tray", None)
        if tray:
            tray.set_state(state, detail)

    def acquire_single_instance_lock(self):
        """Reserve a local port so a second listener cannot create another icon."""
        if self.instance_lock_socket is not None:
            return True
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            lock_socket.bind(("127.0.0.1", 8768))
            lock_socket.listen(1)
        except OSError:
            lock_socket.close()
            return False
        self.instance_lock_socket = lock_socket
        return True

    def _sync_tray_error(self):
        tray = getattr(self, "tray", None)
        if not tray:
            return
        error = getattr(self, "workflow_error", None) or getattr(self, "health_error", None)
        if error:
            tray.set_error(error)
        else:
            tray.clear_error()

    def _set_workflow_error(self, message):
        self.workflow_error = str(message)
        self._sync_tray_error()

    def _clear_workflow_error(self):
        self.workflow_error = None
        self._sync_tray_error()

    def is_service_running(self):
        """Check if the transcription service is running."""
        return self._is_port_open(self.server_port)

    @staticmethod
    def _is_port_open(port):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def is_gpt_service_running(self):
        """Check if the GPT route service is accepting connections."""
        return self._is_port_open(8767)

    def _refresh_service_health(self):
        """Update the recoverable service/audio problem shown on the tray icon."""
        problems = []
        if not self.is_service_running():
            problems.append("transcription service unavailable")
        if not self.is_gpt_service_running():
            problems.append("GPT service unavailable")
        if not self.is_initialized:
            problems.append(self.initialization_error or "audio input unavailable")

        self.health_error = "; ".join(problems) if problems else None
        self._sync_tray_error()
        return not problems

    def wait_for_service(self):
        """Wait for the transcription service to start."""
        self.health_error = "Waiting for transcription service"
        self._sync_tray_error()
        while self.running and not self.is_service_running():
            time.sleep(1)

        if self.running:
            # Pre-initialize audio system for instant response
            self.pre_initialize_audio()
            self._set_tray_state(TrayState.READY)
            self._refresh_service_health()

    def pre_initialize_audio(self):
        """Pre-initialize audio system for instant recording response."""
        try:
            # Test audio devices are available
            devices = sd.query_devices()

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
                # Pre-warm the service connection
                self._warm_service_connection()

            self.is_initialized = True
            self.initialization_error = None

        except Exception as exc:
            self.is_initialized = False
            self.initialization_error = f"audio initialization failed: {exc}"

    def _warm_service_connection(self):
        """Pre-warm the service connection to reduce first-request latency."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            sock.connect(('localhost', self.server_port))
            sock.close()
        except Exception:
            pass

    def record_audio_fast(self):
        """Record audio until ESC is pressed - optimized for instant start."""
        if not self.is_service_running():
            self._set_workflow_error("Transcription service not running")
            self._set_tray_state(TrayState.READY)
            return None

        self.audio_buffer = []
        self.recording = True
        self._set_tray_state(TrayState.RECORDING)

        def audio_callback(indata, frames, time_info, status):
            if self.recording:
                self.audio_buffer.append(indata[:, 0].copy())  # Mono channel

        # Set up listeners for stop recording (ESC key or XButton1)
        def on_key_press_recording(key):
            if key == Key.esc:
                self._stop_recording()
                return False  # Stop listener

        def on_mouse_click_recording(x, y, button, pressed):
            if not pressed:  # Only handle press events
                return
            # Button.x1 (back button - bottom side) for stop recording
            if button == Button.x1:
                self._stop_recording()
                return False  # Stop listener

        keyboard_listener = KeyboardListener(on_press=on_key_press_recording)
        mouse_listener_recording = MouseListener(on_click=on_mouse_click_recording)
        keyboard_listener.start()
        mouse_listener_recording.start()

        try:
            # Use pre-configured audio settings for instant start
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                callback=audio_callback,
                dtype='float32',
                blocksize=int(self.sample_rate * 0.1)  # Pre-configured chunk size
            ):
                start_time = time.time()

                while self.recording:
                    elapsed = time.time() - start_time

                    if elapsed > 180:  # Max 3 minutes
                        self._set_tray_state(TrayState.STOPPING, "Stopping — 3 minute limit reached")
                        self.recording = False
                        break
                    time.sleep(0.1)

        except Exception as e:
            self._set_workflow_error(f"Recording error: {e}")
            self._set_tray_state(TrayState.READY)
            return None

        finally:
            keyboard_listener.stop()
            mouse_listener_recording.stop()

        if not self.audio_buffer:
            self._set_workflow_error("No audio was captured")
            self._set_tray_state(TrayState.READY)
            return None

        # Combine audio chunks
        audio_data = np.concatenate(self.audio_buffer)
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

        This prevents React-based terminal UIs from hitting maximum update depth
        errors caused by rapid individual character inputs.
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

    def paste_text(self, text, recording_mode=None):
        """Handle text output based on recording mode."""
        try:
            # Store in voice buffer
            self.last_transcription = text
            mode = recording_mode or self.recording_mode

            if mode == "normal":
                # Normal mode - paste transcription via clipboard (prevents React update loops)
                self.paste_via_clipboard(text)
                return True

            elif mode == "gpt_direct":
                # GPT direct mode - send only transcription to GPT
                self._set_tray_state(TrayState.GPT_GENERAL)
                response = self.send_to_gpt(text)
                if response:
                    normalized_response = self.normalize_gpt_response(response)
                    self.paste_via_clipboard(normalized_response)
                    return True
                else:
                    self._set_workflow_error("GPT request failed")
                    return False

            elif mode == "gpt_clipboard":
                # GPT with clipboard mode - combine with clipboard and send to GPT
                try:
                    clipboard = pyperclip.paste().strip() if pyperclip.paste() else ""
                except:
                    clipboard = ""

                if clipboard:
                    combined = f"{text}\n\n{clipboard}"
                else:
                    combined = text

                self._set_tray_state(TrayState.GPT_GENERAL)
                response = self.send_to_gpt(combined)
                if response:
                    normalized_response = self.normalize_gpt_response(response)
                    self.paste_via_clipboard(normalized_response)
                    return True
                else:
                    self._set_workflow_error("GPT request failed")
                    return False

            elif mode == "academic_scientific":
                self._set_tray_state(TrayState.GPT_ACADEMIC)
                response = self.send_to_gpt(text, mode="academic_scientific")
                if response:
                    self.paste_via_clipboard(response.strip())
                    return True
                else:
                    self._set_workflow_error("Academic/scientific GPT request failed")
                    return False

        except Exception as e:
            self._set_workflow_error(f"Failed to process: {e}")
            return False
        finally:
            self.recording_mode = "normal"

    def handle_hotkey_trigger(self):
        """Handle the hotkey trigger - record and transcribe with optimized speed."""
        if self.is_initialized:
            audio_data = self.record_audio_fast()
        else:
            audio_data = self.record_audio_fast()

        if audio_data is None:
            return

        # Freeze the mode before transcription/API processing begins. Forward
        # presses after capture ends cannot reclassify this request.
        with self.state_lock:
            self.last_unmodified_forward_at = None
            recording_mode = self.recording_mode

        # Send for transcription
        self._set_tray_state(TrayState.TRANSCRIBING)
        text, error = self.send_transcription_request(audio_data)

        if text:
            # Auto-paste the transcribed text
            success = self.paste_text(text, recording_mode=recording_mode)
            if success:
                self._clear_workflow_error()
                self._refresh_service_health()
        else:
            self._set_workflow_error(f"Transcription failed: {error}")

        self._set_tray_state(TrayState.READY)

    def on_hotkey_triggered(self):
        """Called when Ctrl+Alt+A is pressed."""
        with self.state_lock:
            self.last_unmodified_forward_at = None
            if not self.currently_recording:
                self.recording_mode = "normal"
        self._trigger_recording("keyboard")

    def on_mouse_button_pressed(self, x, y, button, pressed):
        """Called when mouse buttons are pressed (XButtons handled by win32_event_filter)."""
        if not pressed:  # Only handle press events, not release
            return

        # XButton events (x1, x2) are handled by win32_event_filter
        # This callback handles other mouse buttons if needed
        if button not in [Button.x1, Button.x2]:
            pass

    def _trigger_recording(self, source):
        """Common method to trigger recording from keyboard or mouse."""
        with self.state_lock:
            # Prevent duplicate execution
            if self.currently_recording:
                return False

            self.currently_recording = True

        # Trigger transcription in a separate thread to avoid blocking
        thread = threading.Thread(target=self._handle_hotkey_with_cleanup, daemon=True)
        thread.start()
        return True

    def _handle_hotkey_with_cleanup(self):
        """Wrapper to handle hotkey with proper cleanup."""
        try:
            self.handle_hotkey_trigger()
        except Exception as exc:
            self._set_workflow_error(f"Voice workflow failed: {exc}")
        finally:
            with self.state_lock:
                self.currently_recording = False
                self.last_unmodified_forward_at = None
                self.recording_mode = "normal"
            self._set_tray_state(TrayState.READY)

    def send_to_gpt(self, prompt, mode="general"):
        """Send prompt to GPT service and get response."""
        try:
            # Connect to GPT service (port 8767 to avoid conflicts)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)  # 30 second timeout for GPT response
            sock.connect(('localhost', 8767))

            # Prepare request
            request = {
                'action': 'gpt_query',
                'prompt': prompt,
                'mode': mode
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
                return None

            response = json.loads(response_data.decode('utf-8').strip())

            if response.get('success'):
                return response['response']
            else:
                return None

        except Exception:
            return None

    def start_listening(self):
        """Start the global hotkey listener."""
        if not self.acquire_single_instance_lock():
            return
        self.tray.start()
        self._set_tray_state(TrayState.READY, "Starting")
        # Wait for service to be ready
        self.wait_for_service()

        if not self.running:
            return

        # Use proper GlobalHotKeys that don't interfere with normal typing
        try:
            hotkeys = {
                '<ctrl>+<alt>+a': self.on_hotkey_triggered
            }

            # Start mouse listener for global mouse buttons with suppression
            self.mouse_listener = MouseListener(
                on_click=self.on_mouse_button_pressed,
                win32_event_filter=self.win32_event_filter,
                suppress=False  # Use selective suppression via filter
            )
            self.listener_instance = self.mouse_listener  # Store reference for filter
            self.mouse_listener.start()

            with GlobalHotKeys(hotkeys) as hotkey_listener:
                self.hotkey_listener = hotkey_listener
                last_health_check = 0.0

                while self.running:
                    now = time.monotonic()
                    if not self.currently_recording and now - last_health_check >= 5.0:
                        self._refresh_service_health()
                        last_health_check = now
                    time.sleep(0.1)

        except Exception as e:
            self._set_workflow_error(f"Hotkey listener error: {e}")
            self._set_tray_state(TrayState.READY)

    def stop(self):
        """Stop the hotkey and mouse listeners."""
        self.running = False
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.instance_lock_socket:
            self.instance_lock_socket.close()
            self.instance_lock_socket = None
        self.tray.stop()


def signal_handler(signum, frame):
    """Handle shutdown signals."""
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
        listener._set_workflow_error(f"Hotkey listener crashed: {e}")
        listener.stop()
