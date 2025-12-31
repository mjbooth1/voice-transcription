Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\SlideLink\Documents\SlideLink-Toys\voice-transcription"
WshShell.Run chr(34) & "C:\Users\SlideLink\Documents\SlideLink-Toys\voice-transcription\start_service.bat" & Chr(34), 0
Set WshShell = Nothing