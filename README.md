# System-Wide Voice Transcription

Transform your voice to text anywhere on your computer with GPU-accelerated Whisper transcription.

## Quick Start

### 1. Install Additional Dependencies
```bash
# Activate your existing environment
.\venv312\Scripts\activate

# Install the additional packages needed
pip install -r voice-transcription\requirements_additional.txt
```

### 2. Test the Complete System
```bash
# Start both service and hotkey listener
cd voice-transcription
start_service.bat

# System will show:
# - "Loading Whisper model..." (10-15 seconds)
# - "Voice transcription system started!"
# - Two minimized windows: "Voice Service" and "Voice Hotkey"
```

### 3. Set Up Auto-Start (Recommended)
1. Press `Win+R`, type `shell:startup`, press Enter
2. Copy `voice-transcription\start_service.bat` to the Startup folder
3. Restart Windows - both service and hotkey listener start automatically

### 4. No Manual Keyboard Shortcut Needed!
The system now includes a **built-in global hotkey listener**:
- **Press Ctrl+Alt+A anywhere** → Instant voice recording starts
- **Press ESC** → Transcription completes and pastes at cursor
- **Works in any application** without manual setup

## How It Works

### Architecture
- **Background Service**: Keeps Whisper large-v3 loaded in GPU memory
- **Client Script**: Triggered by hotkey, records voice, gets transcription
- **Auto-paste**: Transcribed text appears wherever your cursor is

### Daily Workflow (OPTIMIZED - True Instant Response!)
1. **Login** → Service auto-loads (~10 seconds), hotkey listener starts + pre-initializes audio
2. **Toast**: "🎯 Voice hotkey ready (Ctrl+Alt+A)" 
3. **Press Ctrl+Alt+A anywhere** → **INSTANT** recording starts (0.1 second response!)
4. **Speak** → Real-time recording up to 3 minutes
5. **Press ESC** → Auto-transcribes and pastes at cursor
6. **Repeat** → Every hotkey press is truly instant (audio system pre-loaded)

## Features

- ✅ **GPU-accelerated** Whisper large-v3 (5GB VRAM, instant transcription)
- ✅ **Windows Toast notifications** for status updates
- ✅ **Built-in global hotkey** (Ctrl+Alt+A) - works in any application  
- ✅ **Auto-paste** at cursor position via clipboard
- ✅ **ESC to transcribe** - record as long as you want
- ✅ **Pre-initialized audio system** - 0.1 second response time
- ✅ **Invisible window launch** - VBScript for zero flash
- ✅ **Auto-start** with Windows login (service + optimized hotkey listener)

## Files Created

- `transcription_service.py` - Background service (keeps Whisper model in GPU)
- `hotkey_listener.py` - **OPTIMIZED: Pre-initialized global hotkey listener**
- `launch_transcribe.vbs` - **NEW: Invisible VBScript launcher (no window flash)**
- `transcription_client.py` - Individual recording client (legacy, still works)
- `start_service.bat` - **UPDATED: Starts both service and optimized hotkey listener**
- `start_listener.bat` - Starts just the hotkey listener
- `transcribe_hotkey.bat` - **UPDATED: Uses VBScript for invisible launch**
- `test_service.bat` - Test if service is running
- `requirements_additional.txt` - Extra dependencies needed

## Troubleshooting

### Service Won't Start
- Check if port 8765 is already in use
- Ensure virtual environment has all dependencies
- Look for error toasts or check Task Manager for Python processes

### GPU Not Detected
- Service will automatically fall back to CPU
- Check CUDA installation if GPU transcription fails
- CPU mode still works, just slower

### Hotkey Not Working
- Ensure `transcribe_hotkey.bat` shortcut has correct path
- Try different key combination if conflicts exist
- Run `test_service.bat` to verify service is running

### No Audio Recorded
- Check microphone permissions
- Verify default audio input device
- Test with your existing Streamlit app first

## Performance

- **Initial load**: ~10 seconds (Whisper large-v3 to GPU + audio system pre-init)
- **Hotkey response**: **0.1 seconds** (audio system pre-loaded and ready)
- **VRAM usage**: ~5GB (constant while running)
- **RAM usage**: ~25MB (optimized hotkey listener with pre-loaded audio)
- **Transcription speed**: 2-5 seconds for typical voice clips
- **Accuracy**: Highest quality (large-v3 model)
- **Window flash**: **ELIMINATED** (VBScript invisible launch)

## Security Notes

- All processing is local (no cloud APIs)
- Uses standard Windows Startup folder (IT-friendly)
- Runs as user-level service (no admin rights needed)
- Socket communication only on localhost