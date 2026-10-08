@echo off
setlocal

REM Stop only the Python services launched by start_service.bat in this folder.
set "SERVICE_DIR=%~dp0"

echo Stopping Voice Transcription services...
set "FOUND_SERVICE="

for /f "usebackq delims=" %%P in (`powershell.exe -NoProfile -Command "$root = [IO.Path]::GetFullPath($env:SERVICE_DIR); Get-CimInstance Win32_Process ^| Where-Object { $_.Name -ieq 'pythonw.exe' -and $_.ExecutablePath -and $_.ExecutablePath.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase) -and $_.CommandLine -match '(?i)(transcription_service\.py|gpt_service\.py|hotkey_listener\.py)' } ^| ForEach-Object { $_.ProcessId }"`) do (
    set "FOUND_SERVICE=1"
    echo Stopping process %%P...
    taskkill /PID %%P /T /F >nul 2>&1
)

if defined FOUND_SERVICE (
    echo Voice transcription services stopped.
) else (
    echo No running voice transcription services were found.
)

endlocal
