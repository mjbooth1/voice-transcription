# System-Wide Voice Transcription

Transform your voice to text anywhere on your computer with GPU-accelerated Whisper transcription.

## Quick Start

### 1. Install Dependencies
```bash
# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# For GPU acceleration (recommended):
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

### 2. Configure API Key
```bash
# Edit .env file and add your OpenAI API key
OPENAI_API_KEY=your_key_here
```

### 3. Start the System
```bash
# Start all services
start_service.bat

# System will show:
# - "Loading Whisper model..." (10-15 seconds)
# - "Voice transcription system started!"
```

### 4. Set Up Auto-Start (Recommended)
1. Press `Win+R`, type `shell:startup`, press Enter
2. Copy `start_service.bat` to the Startup folder
3. Restart Windows - all services start automatically

## How to Use

### Mouse Shortcuts (Primary)
| Button | Action |
|--------|--------|
| **Forward** | Record → Transcribe → Type at cursor |
| **Ctrl+Forward** | Record → Send to GPT-4o → Type response |
| **Shift+Forward** | Record + Clipboard → Send to GPT-4o → Type response |
| **Back** or **ESC** | Stop recording |

### Keyboard Shortcut
- **Ctrl+Alt+A** → Start voice recording (same as Forward button)

## Architecture

Three background services run continuously:

| Service | Port | Purpose |
|---------|------|---------|
| `transcription_service.py` | 8765 | GPU-accelerated Whisper transcription |
| `gpt_service.py` | 8767 | GPT-4o text processing |
| `hotkey_listener.py` | - | Global mouse/keyboard listener |

## Files

### Core Services
- `transcription_service.py` - Whisper model management (GPU)
- `gpt_service.py` - GPT-4o API integration
- `hotkey_listener.py` - Global hotkey and mouse button listener

### Configuration
- `.env` - API keys and settings
- `corrections.txt` - Custom transcription corrections
- `requirements.txt` - Python dependencies

### Utilities
- `start_service.bat` - Launch all services
- `button_detector.py` - Debug tool for mouse button detection

## Performance

- **Initial load**: ~10 seconds (Whisper model → GPU)
- **Hotkey response**: ~0.1 seconds
- **VRAM usage**: ~1.3GB (Whisper turbo model)
- **Transcription speed**: 2-5 seconds typical

## Troubleshooting

### Service Won't Start
- Check if ports 8765/8767 are in use
- Verify virtual environment has all dependencies
- Check Task Manager for existing Python processes

### GPU Not Detected
- Service automatically falls back to CPU
- Check NVIDIA drivers are up to date
- CPU mode works, just slower

### No Audio Recorded
- Check microphone permissions
- Verify default audio input device

## Security

- All transcription is local (no cloud except GPT-4o)
- Uses standard Windows Startup folder
- Runs as user-level service (no admin rights)
- Socket communication only on localhost
