import threading
import importlib.util
import json
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


def install_dependency_stubs():
    """Allow logic tests to run without audio/input/OpenAI runtime packages."""
    if importlib.util.find_spec("sounddevice") is None:
        sys.modules["sounddevice"] = types.ModuleType("sounddevice")

    if importlib.util.find_spec("pyperclip") is None:
        pyperclip = types.ModuleType("pyperclip")
        pyperclip.paste = lambda: ""
        pyperclip.copy = lambda _text: None
        sys.modules["pyperclip"] = pyperclip

    if importlib.util.find_spec("pynput") is None:
        pynput = types.ModuleType("pynput")
        keyboard = types.ModuleType("pynput.keyboard")
        mouse = types.ModuleType("pynput.mouse")

        keyboard.Key = types.SimpleNamespace(esc="esc", ctrl="ctrl")
        keyboard.Listener = MagicMock
        keyboard.GlobalHotKeys = MagicMock
        keyboard.Controller = MagicMock
        mouse.Button = types.SimpleNamespace(x1="x1", x2="x2")
        mouse.Listener = MagicMock
        pynput.keyboard = keyboard
        pynput.mouse = mouse
        sys.modules.update(
            {
                "pynput": pynput,
                "pynput.keyboard": keyboard,
                "pynput.mouse": mouse,
            }
        )

    if importlib.util.find_spec("openai") is None:
        openai = types.ModuleType("openai")
        openai.OpenAI = MagicMock
        sys.modules["openai"] = openai

    if importlib.util.find_spec("dotenv") is None:
        dotenv = types.ModuleType("dotenv")
        dotenv.load_dotenv = lambda: None
        sys.modules["dotenv"] = dotenv


install_dependency_stubs()

import hotkey_listener
from academic_scientific import load_academic_scientific_prompt
import gpt_service
from gpt_service import GENERAL_SYSTEM_PROMPT, GPTService
from hotkey_listener import GlobalHotkeyListener
from tray_indicator import TrayState


def make_listener(window_seconds=0.5):
    """Build the gesture-relevant listener state without OS device setup."""
    listener = GlobalHotkeyListener.__new__(GlobalHotkeyListener)
    listener.state_lock = threading.Lock()
    listener.currently_recording = False
    listener.recording = False
    listener.recording_mode = "normal"
    listener.last_unmodified_forward_at = None
    listener.double_forward_window_seconds = window_seconds
    listener.tray = MagicMock()
    listener.health_error = None
    listener.workflow_error = None

    def trigger(_source):
        listener.currently_recording = True
        return True

    listener._trigger_recording = MagicMock(side_effect=trigger)
    return listener


class DoubleForwardGestureTests(unittest.TestCase):
    def test_single_forward_starts_normal_recording_immediately(self):
        listener = make_listener()

        result = listener._handle_forward_press(pressed_at=10.0)

        self.assertEqual(result, "started")
        self.assertEqual(listener.recording_mode, "normal")
        listener._trigger_recording.assert_called_once_with("mouse_forward_normal")

    def test_second_forward_within_window_promotes_active_recording(self):
        listener = make_listener()
        listener._handle_forward_press(pressed_at=10.0)

        result = listener._handle_forward_press(pressed_at=10.4)

        self.assertEqual(result, "academic_scientific")
        self.assertEqual(listener.recording_mode, "academic_scientific")
        self.assertIsNone(listener.last_unmodified_forward_at)
        self.assertEqual(listener._trigger_recording.call_count, 1)

    def test_boundary_is_inclusive_and_later_press_is_ignored(self):
        listener = make_listener()
        listener._handle_forward_press(pressed_at=10.0)
        self.assertEqual(
            listener._handle_forward_press(pressed_at=10.5),
            "academic_scientific",
        )

        listener = make_listener()
        listener._handle_forward_press(pressed_at=10.0)
        self.assertEqual(listener._handle_forward_press(pressed_at=10.501), "ignored")
        self.assertEqual(listener.recording_mode, "normal")

    def test_third_press_does_not_start_or_reclassify_again(self):
        listener = make_listener()
        listener._handle_forward_press(pressed_at=10.0)
        listener._handle_forward_press(pressed_at=10.2)

        self.assertEqual(listener._handle_forward_press(pressed_at=10.3), "ignored")
        self.assertEqual(listener.recording_mode, "academic_scientific")
        self.assertEqual(listener._trigger_recording.call_count, 1)

    def test_modified_modes_start_immediately_and_cannot_form_double_forward(self):
        listener = make_listener()
        listener.last_unmodified_forward_at = 9.9

        result = listener._handle_forward_press(ctrl_pressed=True, pressed_at=10.0)

        self.assertEqual(result, "started")
        self.assertEqual(listener.recording_mode, "gpt_direct")
        self.assertIsNone(listener.last_unmodified_forward_at)

        self.assertEqual(listener._handle_forward_press(pressed_at=10.1), "ignored")
        self.assertEqual(listener.recording_mode, "gpt_direct")

    def test_back_stop_clears_pending_gesture(self):
        listener = make_listener()
        listener._handle_forward_press(pressed_at=10.0)
        listener.recording = True

        listener._stop_recording()

        self.assertFalse(listener.recording)
        self.assertIsNone(listener.last_unmodified_forward_at)
        listener.tray.set_state.assert_called_with(TrayState.STOPPING, None)

    def test_windows_interval_is_honored_but_capped(self):
        with patch.object(hotkey_listener, "GetDoubleClickTime", return_value=300):
            self.assertEqual(hotkey_listener.get_double_forward_window_seconds(), 0.3)

        with patch.object(hotkey_listener, "GetDoubleClickTime", return_value=1200):
            self.assertEqual(hotkey_listener.get_double_forward_window_seconds(), 0.5)

        with patch.object(hotkey_listener, "GetDoubleClickTime", side_effect=OSError):
            self.assertEqual(hotkey_listener.get_double_forward_window_seconds(), 0.5)


class GPTAcademicRoutingTests(unittest.TestCase):
    def make_service(self):
        service = GPTService.__new__(GPTService)
        service.model = "gpt-6-sol"
        service.reasoning_effort = "none"
        service.max_output_tokens = 2000
        service.client = MagicMock()
        completion = MagicMock()
        completion.choices = [MagicMock(message=MagicMock(content="  Cleaned prose.  "))]
        service.client.chat.completions.create.return_value = completion
        return service

    def test_general_mode_keeps_existing_system_prompt(self):
        service = self.make_service()

        result, error = service.process_gpt_request("Draft text")

        self.assertEqual((result, error), ("Cleaned prose.", None))
        request = service.client.chat.completions.create.call_args.kwargs
        self.assertEqual(request["messages"][0]["content"], GENERAL_SYSTEM_PROMPT)

    def test_academic_mode_uses_dedicated_system_prompt(self):
        service = self.make_service()

        service.process_gpt_request("Dictated text", mode="academic_scientific")

        request = service.client.chat.completions.create.call_args.kwargs
        self.assertEqual(
            request["messages"][0]["content"],
            load_academic_scientific_prompt(),
        )
        self.assertEqual(request["messages"][1], {"role": "user", "content": "Dictated text"})

    def test_all_modes_use_no_reasoning_and_no_sampling_overrides(self):
        for mode in ("general", "academic_scientific"):
            with self.subTest(mode=mode):
                service = self.make_service()
                service.process_gpt_request("Draft text", mode=mode)

                request = service.client.chat.completions.create.call_args.kwargs
                self.assertEqual(request["model"], "gpt-6-sol")
                self.assertEqual(request["reasoning_effort"], "none")
                self.assertNotIn("temperature", request)
                self.assertNotIn("top_p", request)

    def test_service_defaults_to_sol_without_reasoning(self):
        service = GPTService.__new__(GPTService)
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True),
            patch.object(gpt_service, "load_dotenv"),
            patch.object(gpt_service, "OpenAI", return_value=MagicMock()),
        ):
            initialized = service.initialize_openai()

        self.assertTrue(initialized)
        self.assertEqual(service.model, "gpt-6-sol")
        self.assertEqual(service.reasoning_effort, "none")
        self.assertEqual(service.max_output_tokens, 2000)

    def test_example_configuration_documents_sol_without_reasoning(self):
        project_root = Path(__file__).resolve().parents[1]
        example_config = (project_root / ".env.example").read_text(encoding="utf-8")
        readme = (project_root / "README.md").read_text(encoding="utf-8")

        for content in (example_config, readme):
            self.assertIn("GPT_MODEL=gpt-6-sol", content)
            self.assertIn("GPT_REASONING_EFFORT=none", content)

    def test_academic_prompt_forbids_added_pretentious_transitions(self):
        prompt = load_academic_scientific_prompt()
        for phrase in ("nonetheless", "furthermore", "moreover", "it is worth noting"):
            self.assertIn(phrase, prompt)
        self.assertIn("Do not introduce formal, ornamental, or stock transitions", prompt)
        self.assertIn("Preserve such wording when it was genuinely present", prompt)
        self.assertIn("Preserve hedging and epistemic strength exactly", prompt)
        self.assertIn("Do not invent or add explanations", prompt)

    def test_academic_response_is_trimmed_and_pasted_once(self):
        listener = GlobalHotkeyListener.__new__(GlobalHotkeyListener)
        listener.last_transcription = ""
        listener.recording_mode = "academic_scientific"
        listener.send_to_gpt = MagicMock(return_value="  Revised paragraph.  ")
        listener.paste_via_clipboard = MagicMock()
        listener.tray = MagicMock()
        listener.health_error = None
        listener.workflow_error = None

        listener.paste_text("Raw dictation", recording_mode="academic_scientific")

        listener.send_to_gpt.assert_called_once_with(
            "Raw dictation",
            mode="academic_scientific",
        )
        listener.tray.set_state.assert_called_once_with(TrayState.GPT_ACADEMIC, None)
        listener.paste_via_clipboard.assert_called_once_with("Revised paragraph.")

    def test_academic_mode_is_serialized_to_gpt_service(self):
        listener = GlobalHotkeyListener.__new__(GlobalHotkeyListener)
        fake_socket = MagicMock()
        fake_socket.recv.side_effect = [
            b'{"success": true, "response": "Revised paragraph."}\n'
        ]

        with patch.object(hotkey_listener.socket, "socket", return_value=fake_socket):
            response = listener.send_to_gpt(
                "Raw dictation",
                mode="academic_scientific",
            )

        self.assertEqual(response, "Revised paragraph.")
        payload = json.loads(fake_socket.send.call_args.args[0].decode("utf-8"))
        self.assertEqual(payload["action"], "gpt_query")
        self.assertEqual(payload["mode"], "academic_scientific")
        self.assertEqual(payload["prompt"], "Raw dictation")


if __name__ == "__main__":
    unittest.main()
