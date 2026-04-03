' DualVoicer Launcher - Starts the main app with hidden console
' This VBS script ensures the console window is never visible

Set WshShell = CreateObject("WScript.Shell")

' Get the directory where this script is located
strPath = WScript.ScriptFullName
Set objFSO = CreateObject("Scripting.FileSystemObject")
strFolder = objFSO.GetParentFolderName(strPath)

' Path to the main EXE
strExe = strFolder & "\DualVoicer_v3.6.5.exe"

' Run the EXE with hidden window (0 = vbHide)
WshShell.Run """" & strExe & """", 0, False

Set WshShell = Nothing
Set objFSO = Nothing
