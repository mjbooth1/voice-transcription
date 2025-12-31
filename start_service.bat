@echo off
REM Start the voice transcription and prompt enhancement background services
REM This file goes in Windows Startup folder for auto-start

echo Starting Voice Transcription and Prompt Enhancement Services...

REM Get the directory where this batch file is located
set SCRIPT_DIR=%~dp0

REM Activate the Python virtual environment
call "%SCRIPT_DIR%venv\Scripts\activate.bat"

REM Change to the voice-transcription directory
cd /d "%SCRIPT_DIR%"

REM Start transcription and new unified GPT services
echo Starting Voice Transcription and GPT-4o Command Center...
echo Loading Whisper turbo model and GPT-4o connection (this may take 10-15 seconds)...

REM Start the transcription service invisibly
cd /d "%SCRIPT_DIR%"
start "Voice Service" pythonw transcription_service.py

REM Wait a moment for service to initialize
timeout /t 2 /nobreak >nul

REM Start the new GPT-4o service invisibly
echo Starting GPT-4o service...
start "GPT Service" pythonw gpt_service.py

REM Wait a moment for GPT service to initialize
timeout /t 2 /nobreak >nul

REM Start TTS services based on configuration
echo Starting TTS services...

REM Always start OpenAI TTS service (for fallback)
start "OpenAI TTS Service" pythonw tts_service.py

REM Wait a moment for OpenAI TTS service to initialize
timeout /t 2 /nobreak >nul

REM Check if local TTS should be started (simplified check)
REM Note: This is a basic check - the service will determine the actual mode
echo Starting Local TTS service (conditional based on TTS_MODE)...
start "Local TTS Service" pythonw local_tts_service.py

REM Wait a moment for Local TTS service to initialize
timeout /t 2 /nobreak >nul

REM Start the voice hotkey listener (windowless) - now includes Ctrl+Alt+Q
echo Starting voice hotkey listener with GPT command...
start "Voice Hotkey" pythonw hotkey_listener.py

echo Voice transcription and GPT-4o DUAL TTS command center started!
echo - Transcription service running with GPU-loaded turbo model
echo - GPT-4o service ready for flexible AI commands
echo - DUAL TTS system: OpenAI + Local Piper (switch via TTS_MODE)
echo - Voice hotkey listener ready with mouse button support
echo.
echo Available modes:
echo   * Forward button - Normal recording (types at cursor)
echo   * Ctrl+Forward - GPT direct mode (transcription only)
echo   * Shift+Forward - GPT with clipboard (transcription + clipboard)
echo   * Alt+Forward - VOICE MODE (speak → GPT → hear response)
echo   * Back button or Escape - Stop recording or abort TTS playback
echo   * Ctrl+Alt+A - Keyboard fallback for Forward
echo.
echo All services are now running independently.
echo Voice transcriptions bypass clipboard - your Ctrl+C/Ctrl+V works normally!