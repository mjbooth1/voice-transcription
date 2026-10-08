# System-Wide Voice Transcription

Transform your voice to text anywhere on your Windows computer with GPU-accelerated Whisper transcription.

## Quick Start

### 1. Clone and Install Dependencies

```bash
git clone https://github.com/SlideLink/voice-transcription.git
cd voice-transcription

python -m venv venv
.\venv\Scripts\activate

pip install -r requirements.txt

# GPU acceleration is recommended for Whisper turbo.
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

### 2. Configure API Key

```bash
copy .env.example .env
```

Edit `.env` and set:

```env
OPENAI_API_KEY=your_key_here
GPT_MODEL=gpt-6-sol
GPT_REASONING_EFFORT=none
GPT_MAX_OUTPUT_TOKENS=2000
```

### 3. Start the System

```bash
start_service.bat
```

The first run may take longer while Whisper downloads/warms the local model cache.
When the listener starts, a microphone appears in the Windows notification area.
Windows may place new icons in the tray overflow menu until you pin or drag the
icon beside the clock.

### 4. Set Up Auto-Start

1. Press `Win+R`, type `shell:startup`, and press Enter.
2. Copy `start_service.bat` to the Startup folder.
3. Restart Windows.

## How to Use

### Mouse Shortcuts

| Button | Action |
|--------|--------|
| **Forward** | Record -> Transcribe -> Paste at cursor |
| **Double Forward** | Record -> Academic/Scientific revision -> Paste at cursor |
| **Ctrl+Forward** | Record -> Send to GPT-6 Sol -> Paste response |
| **Shift+Forward** | Record + Clipboard -> Send to GPT-6 Sol -> Paste response |
| **Back** or **ESC** | Stop recording |

### Keyboard Shortcut

- **Ctrl+Alt+A** -> Start voice recording.

### Tray Microphone Status

The icon uses a fixed white microphone on a large circular background. The
background color and hover text replace the former toast banners:

| Appearance | Status |
|------------|--------|
| **Gray background** | Ready |
| **Green background** | Recording |
| **Red background** | Stopping and assembling captured audio |
| **Blue background** | Whisper transcription in progress |
| **Orange background** | Ctrl+Forward or Shift+Forward GPT request in progress |
| **Purple background** | Academic/scientific GPT request in progress |
| **Small red badge** | A service, audio, timeout, or processing problem; hover for details |

The tray icon intentionally has no click action or menu. Use `stop_service.bat`
to stop the background processes.

## Architecture

Three background services run continuously:

| Service | Port | Purpose |
|---------|------|---------|
| `transcription_service.py` | 8765 | GPU-accelerated Whisper transcription |
| `gpt_service.py` | 8767 | GPT-6 Sol text processing |
| `hotkey_listener.py` | - | Global mouse/keyboard listener |

## Files

### Core Services

- `transcription_service.py` - Whisper model management.
- `gpt_service.py` - GPT-6 Sol API integration.
- `academic_scientific_prompt.md` - Editable academic/scientific revision prompt; changes apply on the next academic request.
- `academic_scientific.py` - Loads the editable prompt for each academic request.
- `hotkey_listener.py` - Global hotkey and mouse button listener.
- `tray_indicator.py` - Thread-safe tray icon rendering and status lifecycle.
- `Microphone.ico` - Retained legacy handheld-microphone artwork; the active tray
  foreground is the upright microphone rendered by `tray_indicator.py`.

### Configuration

- `.env.example` - Template for local API keys and settings.
- `.env` - Local API keys and settings; ignored by Git.
- `corrections.txt` - Custom transcription corrections.
- `requirements.txt` - Python dependencies.

### Utilities

- `start_service.bat` - Launch all services.
- `button_detector.py` - Debug tool for mouse button detection.

## Portability Notes

- `venv/`, `.env`, `models/`, runtime audio, and Python caches are ignored by Git.
- Whisper model files should be downloaded locally on each machine, not committed.
- Install current NVIDIA drivers and CUDA-compatible PyTorch on machines where GPU acceleration is needed.
- The GPT service uses Chat Completions for compatibility with work networks that block the Responses API endpoint.

## Troubleshooting

### Service Won't Start

- Check if ports 8765/8767 are in use.
- Verify the virtual environment has all dependencies installed.
- Check Task Manager for existing Python processes.
- Hover over a red-badged microphone for the current service or audio error.

### Tray Icon Is Not Beside the Clock

- Check the Windows notification-area overflow menu (`^`).
- Drag the microphone beside the clock or enable it in taskbar tray settings.
- Windows controls icon pinning; the listener cannot force this preference.

### Duplicate or Old Tray Icon

1. Run `stop_service.bat` once to stop every voice-transcription process from
   this project.
2. Move the pointer over any icon that remains; Windows removes stale tray icons
   when it refreshes them.
3. Run `start_service.bat` once.

The listener holds localhost port 8768 as a single-instance lock, so subsequent
starts exit without creating another tray icon.

### Legacy Toast Notifications

Toast imports and display implementations remain as commented migration
references in the service files, but they are intentionally non-executable.
All active user feedback comes from the tray microphone.

### GPU Not Detected

- The service automatically falls back to CPU.
- Check that NVIDIA drivers are installed and up to date.
- CPU mode works, but it is slower.

### No Audio Recorded

- Check microphone permissions.
- Verify the default audio input device.

## Security

- All transcription is local except GPT-6 Sol processing.
- OpenAI credentials live in `.env`, which is ignored by Git.
- Socket communication is local-only.
