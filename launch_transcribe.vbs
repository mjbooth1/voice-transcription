Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Get the directory where this VBS file is located
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)
projectDir = fso.GetParentFolderName(currentDir)

' Build the command to run with pythonw (windowless)
pythonPath = projectDir & "\venv312\Scripts\pythonw.exe"
scriptPath = currentDir & "\transcription_client.py"

' Change to the voice-transcription directory and run the Python script
command = "cmd /c ""cd /d """ & currentDir & """ && """ & pythonPath & """ """ & scriptPath & """"

' Run completely hidden (0 = hidden, False = don't wait)
WshShell.Run command, 0, False