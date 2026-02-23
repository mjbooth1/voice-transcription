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

REM Start transcription and GPT services
echo Starting Voice Transcription and GPT Service...
echo Loading Whisper turbo model and GPT connection (this may take 10-15 seconds)...

REM Start the transcription service invisibly
start "Voice Service" pythonw transcription_service.py

REM Wait a moment for service to initialize
timeout /t 2 /nobreak >nul

REM Start the GPT service invisibly
echo Starting GPT service...
start "GPT Service" pythonw gpt_service.py

REM Wait a moment for GPT service to initialize
timeout /t 2 /nobreak >nul

REM Start the voice hotkey listener (windowless)
echo Starting voice hotkey listener...
start "Voice Hotkey" pythonw hotkey_listener.py

echo.
echo Voice transcription services started!
echo - Transcription service (Whisper turbo, GPU-accelerated)
echo - GPT service (model from .env)
echo - Hotkey listener (mouse/keyboard)
echo.
echo Hotkeys:
echo   Forward button     - Normal transcription
echo   Ctrl+Forward       - GPT mode
echo   Shift+Forward      - GPT + clipboard
echo   Back/Escape        - Stop recording
echo   Ctrl+Alt+A         - Keyboard fallback