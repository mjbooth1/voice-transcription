import importlib.util
import sys
import threading
from pathlib import Path
import types
import unittest
from unittest.mock import MagicMock

from tray_indicator import TrayIndicator, TrayState


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def install_hotkey_dependency_stubs():
    """Allow workflow tests to run without Windows input/audio packages."""
    if "sounddevice" not in sys.modules and importlib.util.find_spec("sounddevice") is None:
        sys.modules["sounddevice"] = types.ModuleType("sounddevice")

    if "pyperclip" not in sys.modules and importlib.util.find_spec("pyperclip") is None:
        pyperclip = types.ModuleType("pyperclip")
        pyperclip.paste = lambda: ""
        pyperclip.copy = lambda _text: None
        sys.modules["pyperclip"] = pyperclip

    if "pynput" not in sys.modules and importlib.util.find_spec("pynput") is None:
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


install_hotkey_dependency_stubs()


class FakeIcon:
    def __init__(self, name, icon, title, menu=None):
        self.name = name
        self.icon = icon
        self.title = title
        self.menu = menu
        self.run_detached_called = False
        self.stop_called = False

    def run_detached(self):
        self.run_detached_called = True

    def stop(self):
        self.stop_called = True


class TrayIndicatorTests(unittest.TestCase):
    def test_all_states_render_as_colored_circles_with_white_microphones(self):
        indicator = TrayIndicator(PROJECT_ROOT / "Microphone.ico")

        for state in TrayState:
            with self.subTest(state=state):
                image = indicator.render_icon(state=state, size=64)
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.size, (64, 64))
                self.assertEqual(image.getpixel((0, 0))[3], 0)
                colors = {
                    color[:3]
                    for _count, color in image.getcolors(maxcolors=64 * 64)
                }
                self.assertIn(state.color[:3], colors)
                self.assertIn((255, 255, 255), colors)
                self.assertEqual(image.getpixel((8, 32))[:3], state.color[:3])

    def test_problem_badge_is_distinct_from_red_stopping_background(self):
        indicator = TrayIndicator(PROJECT_ROOT / "Microphone.ico")
        ready_problem = indicator.render_icon(TrayState.READY, has_error=True, size=64)
        stopping = indicator.render_icon(TrayState.STOPPING, has_error=False, size=64)

        self.assertEqual(ready_problem.getpixel((55, 9))[:3], (225, 30, 30))
        self.assertNotEqual(stopping.getpixel((55, 9))[:3], (225, 30, 30))

    def test_missing_old_icon_still_uses_standing_microphone(self):
        indicator = TrayIndicator(PROJECT_ROOT / "does-not-exist.ico")
        image = indicator.render_icon(size=64)

        self.assertIsNotNone(image.getchannel("A").getbbox())
        self.assertEqual(image.getpixel((0, 0))[3], 0)

    def test_standing_microphone_is_taller_than_it_is_wide(self):
        indicator = TrayIndicator(PROJECT_ROOT / "Microphone.ico")
        mask_box = indicator._source.getchannel("A").getbbox()

        self.assertIsNotNone(mask_box)
        width = mask_box[2] - mask_box[0]
        height = mask_box[3] - mask_box[1]
        self.assertGreater(height, width)

    def test_start_creates_one_menu_less_icon_and_stop_removes_it(self):
        created = []

        def factory(*args, **kwargs):
            icon = FakeIcon(*args, **kwargs)
            created.append(icon)
            return icon

        indicator = TrayIndicator(PROJECT_ROOT / "Microphone.ico", icon_factory=factory)

        self.assertTrue(indicator.start())
        self.assertTrue(indicator.start())
        self.assertEqual(len(created), 1)
        self.assertIsNone(created[0].menu)
        self.assertTrue(created[0].run_detached_called)

        indicator.stop()
        self.assertTrue(created[0].stop_called)

    def test_state_error_and_tooltip_updates_are_thread_safe(self):
        icon = FakeIcon("name", None, "title")
        indicator = TrayIndicator(
            PROJECT_ROOT / "Microphone.ico",
            icon_factory=lambda *_args, **_kwargs: icon,
        )
        indicator.start()

        threads = [
            threading.Thread(target=indicator.set_state, args=(state,))
            for state in TrayState
        ]
        threads.append(threading.Thread(target=indicator.set_error, args=("microphone unavailable",)))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertIn("Voice Transcription", indicator.title)
        self.assertIn("Problem: microphone unavailable", indicator.title)
        self.assertLessEqual(len(indicator.title), 127)


class TrayWorkflowTests(unittest.TestCase):
    def make_listener(self, mode, gpt_response="Processed text"):
        from hotkey_listener import GlobalHotkeyListener

        listener = GlobalHotkeyListener.__new__(GlobalHotkeyListener)
        listener.state_lock = threading.Lock()
        listener.tray = MagicMock()
        listener.health_error = None
        listener.workflow_error = None
        listener.initialization_error = None
        listener.recording_mode = mode
        listener.last_unmodified_forward_at = None
        listener.is_initialized = True
        listener.last_transcription = ""
        listener.paste_via_clipboard = MagicMock()
        listener.send_to_gpt = MagicMock(return_value=gpt_response)
        listener.send_transcription_request = MagicMock(return_value=("Raw text", None))
        listener._refresh_service_health = MagicMock(return_value=True)

        def record():
            listener._set_tray_state(TrayState.RECORDING)
            listener._set_tray_state(TrayState.STOPPING)
            return object()

        listener.record_audio_fast = MagicMock(side_effect=record)
        return listener

    @staticmethod
    def states(listener):
        return [call.args[0] for call in listener.tray.set_state.call_args_list]

    def test_normal_route_state_sequence(self):
        listener = self.make_listener("normal")
        listener.handle_hotkey_trigger()

        self.assertEqual(
            self.states(listener),
            [
                TrayState.RECORDING,
                TrayState.STOPPING,
                TrayState.TRANSCRIBING,
                TrayState.READY,
            ],
        )

    def test_ctrl_and_shift_routes_use_orange_only_during_gpt(self):
        for mode in ("gpt_direct", "gpt_clipboard"):
            with self.subTest(mode=mode):
                listener = self.make_listener(mode)
                listener.handle_hotkey_trigger()
                self.assertEqual(
                    self.states(listener),
                    [
                        TrayState.RECORDING,
                        TrayState.STOPPING,
                        TrayState.TRANSCRIBING,
                        TrayState.GPT_GENERAL,
                        TrayState.READY,
                    ],
                )

    def test_academic_route_uses_purple_only_during_gpt(self):
        listener = self.make_listener("academic_scientific")
        listener.handle_hotkey_trigger()

        self.assertEqual(
            self.states(listener),
            [
                TrayState.RECORDING,
                TrayState.STOPPING,
                TrayState.TRANSCRIBING,
                TrayState.GPT_ACADEMIC,
                TrayState.READY,
            ],
        )

    def test_failure_returns_ready_with_problem_badge(self):
        listener = self.make_listener("normal")
        listener.send_transcription_request.return_value = (None, "service timeout")

        listener.handle_hotkey_trigger()

        listener.tray.set_error.assert_called_with("Transcription failed: service timeout")
        self.assertEqual(self.states(listener)[-1], TrayState.READY)


if __name__ == "__main__":
    unittest.main()
