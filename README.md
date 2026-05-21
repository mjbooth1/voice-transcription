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
GPT_MODEL=gpt-4o
```

### 3. Start the System

```bash
start_service.bat
```

The first run may take longer while Whisper downloads/warms the local model cache.

### 4. Set Up Auto-Start

1. Press `Win+R`, type `shell:startup`, and press Enter.
2. Copy `start_service.bat` to the Startup folder.
3. Restart Windows.

## How to Use

### Mouse Shortcuts

| Button | Action |
|--------|--------|
| **Forward** | Record -> Transcribe -> Paste at cursor |
| **Ctrl+Forward** | Record -> Send to GPT-4o -> Paste response |
| **Shift+Forward** | Record + Clipboard -> Send to GPT-4o -> Paste response |
| **Back** or **ESC** | Stop recording |

### Keyboard Shortcut

- **Ctrl+Alt+A** -> Start voice recording.

## Architecture

Three background services run continuously:

| Service | Port | Purpose |
|---------|------|---------|
| `transcription_service.py` | 8765 | GPU-accelerated Whisper transcription |
| `gpt_service.py` | 8767 | GPT-4o text processing |
| `hotkey_listener.py` | - | Global mouse/keyboard listener |

## Files

### Core Services

- `transcription_service.py` - Whisper model management.
- `gpt_service.py` - GPT-4o API integration.
- `hotkey_listener.py` - Global hotkey and mouse button listener.

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

## Troubleshooting

### Service Won't Start

- Check if ports 8765/8767 are in use.
- Verify the virtual environment has all dependencies installed.
- Check Task Manager for existing Python processes.

### GPU Not Detected

- The service automatically falls back to CPU.
- Check that NVIDIA drivers are installed and up to date.
- CPU mode works, but it is slower.

### No Audio Recorded

- Check microphone permissions.
- Verify the default audio input device.

## Security

- All transcription is local except GPT-4o processing.
- OpenAI credentials live in `.env`, which is ignored by Git.
- Socket communication is local-only.
