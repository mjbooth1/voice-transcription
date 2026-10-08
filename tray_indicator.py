"""Thread-safe Windows system-tray status indicator for voice transcription."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
import threading
from typing import Callable, Optional

from PIL import Image, ImageDraw


class TrayState(Enum):
    READY = ("Ready", (128, 128, 128, 255))
    RECORDING = ("Recording", (34, 177, 76, 255))
    STOPPING = ("Stopping", (210, 48, 48, 255))
    TRANSCRIBING = ("Transcribing", (38, 114, 221, 255))
    GPT_GENERAL = ("GPT processing", (238, 126, 34, 255))
    GPT_ACADEMIC = ("Academic/scientific processing", (143, 68, 173, 255))

    @property
    def label(self) -> str:
        return self.value[0]

    @property
    def color(self) -> tuple[int, int, int, int]:
        return self.value[1]


class TrayIndicator:
    """Own and update a microphone icon in the Windows notification area."""

    def __init__(
        self,
        icon_path: Optional[Path | str] = None,
        icon_factory: Optional[Callable[..., object]] = None,
    ) -> None:
        self.icon_path = Path(icon_path or Path(__file__).with_name("Microphone.ico"))
        self._icon_factory = icon_factory
        self._icon = None
        self._state = TrayState.READY
        self._detail: Optional[str] = None
        self._error: Optional[str] = None
        self._lock = threading.RLock()
        self._source = self._load_source_icon()
        self._images: dict[tuple[TrayState, bool, int], Image.Image] = {}

    @property
    def state(self) -> TrayState:
        with self._lock:
            return self._state

    @property
    def error(self) -> Optional[str]:
        with self._lock:
            return self._error

    @property
    def title(self) -> str:
        with self._lock:
            return self._build_title()

    def start(self) -> bool:
        """Create the tray icon without blocking the listener's main loop."""
        with self._lock:
            if self._icon is not None:
                return True

            try:
                factory = self._icon_factory
                if factory is None:
                    import pystray

                    factory = pystray.Icon

                self._icon = factory(
                    "voice-transcription",
                    self.render_icon(),
                    self._build_title(),
                    menu=None,
                )
                self._icon.run_detached()
                return True
            except Exception:
                self._icon = None
                return False

    def set_state(self, state: TrayState, detail: Optional[str] = None) -> None:
        with self._lock:
            self._state = state
            self._detail = detail
            self._publish()

    def set_error(self, message: str) -> None:
        with self._lock:
            self._error = str(message).strip() or "Unknown problem"
            self._publish()

    def clear_error(self) -> None:
        with self._lock:
            self._error = None
            self._publish()

    def stop(self) -> None:
        with self._lock:
            icon = self._icon
            self._icon = None
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                pass

    def render_icon(
        self,
        state: Optional[TrayState] = None,
        has_error: Optional[bool] = None,
        size: int = 64,
    ) -> Image.Image:
        """Return a white microphone on a state-colored circular background."""
        with self._lock:
            state = state or self._state
            has_error = bool(self._error) if has_error is None else has_error
            cache_key = (state, has_error, size)
            cached = self._images.get(cache_key)
            if cached is not None:
                return cached.copy()

            # Draw oversized and downsample so the circular edge and microphone
            # remain clean at Windows' common 16px and 24px tray sizes.
            render_size = max(256, size * 4)
            result = Image.new("RGBA", (render_size, render_size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(result)
            margin = max(2, round(render_size * 0.025))
            draw.ellipse(
                (margin, margin, render_size - margin, render_size - margin),
                fill=state.color,
            )

            microphone_size = round(render_size * 0.68)
            source = self._source.resize(
                (microphone_size, microphone_size),
                Image.Resampling.LANCZOS,
            )
            microphone = Image.new(
                "RGBA",
                (microphone_size, microphone_size),
                (255, 255, 255, 255),
            )
            microphone.putalpha(source.getchannel("A"))
            microphone_offset = (render_size - microphone_size) // 2
            result.alpha_composite(
                microphone,
                (microphone_offset, microphone_offset),
            )

            if has_error:
                outer = max(24, round(render_size * 0.27))
                badge_margin = max(2, round(render_size * 0.015))
                box = (
                    render_size - outer - badge_margin,
                    badge_margin,
                    render_size - badge_margin,
                    outer + badge_margin,
                )
                draw.ellipse(box, fill=(255, 255, 255, 255))
                inset = max(3, round(render_size * 0.035))
                inner = tuple(
                    value + inset if index < 2 else value - inset
                    for index, value in enumerate(box)
                )
                draw.ellipse(inner, fill=(225, 30, 30, 255))

            result = result.resize((size, size), Image.Resampling.LANCZOS)
            self._images[cache_key] = result
            return result.copy()

    def _load_source_icon(self) -> Image.Image:
        # Use an original upright studio-microphone silhouette based on the
        # supplied reference. The old ICO contains the unwanted long handheld
        # microphone and is intentionally not used as the tray foreground.
        return self._draw_standing_microphone()

    @staticmethod
    def _draw_standing_microphone(size: int = 256) -> Image.Image:
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        fill = (255, 255, 255, 255)
        width = round(size * 0.29)
        left = (size - width) // 2
        top = round(size * 0.12)
        bottom = round(size * 0.58)
        draw.rounded_rectangle(
            (left, top, left + width, bottom),
            radius=width // 2,
            fill=fill,
        )
        stroke = max(8, round(size * 0.065))
        draw.arc(
            (
                round(size * 0.27),
                round(size * 0.34),
                round(size * 0.73),
                round(size * 0.79),
            ),
            start=0,
            end=180,
            fill=fill,
            width=stroke,
        )
        draw.line(
            (
                size // 2,
                round(size * 0.78),
                size // 2,
                round(size * 0.88),
            ),
            fill=fill,
            width=stroke,
        )
        draw.rounded_rectangle(
            (
                round(size * 0.36),
                round(size * 0.86),
                round(size * 0.64),
                round(size * 0.93),
            ),
            radius=max(2, stroke // 4),
            fill=fill,
        )
        return image

    def _build_title(self) -> str:
        status = self._detail or self._state.label
        title = f"Voice Transcription — {status}"
        if self._error:
            title += f" — Problem: {self._error}"
        return title[:127]

    def _publish(self) -> None:
        if self._icon is None:
            return
        try:
            self._icon.icon = self.render_icon()
            self._icon.title = self._build_title()
        except Exception:
            pass
