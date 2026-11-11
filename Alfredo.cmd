@echo off
setlocal
start "" /D "%~dp0" "%~dp0.venv\Scripts\pythonw.exe" -B "%~dp0scripts\alfredo_control.py"
endlocal
