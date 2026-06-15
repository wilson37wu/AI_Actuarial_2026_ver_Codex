@echo off
REM Phase IGUI Task 8 - one-click offline launcher (Windows).
REM Double-click this file. It starts the local Actuarial Input & Run GUI on
REM 127.0.0.1 and opens your browser. Fully offline; no install needed beyond
REM Python 3.8+ (input entry + browsing work even without numpy/scipy; the
REM compute step needs them - the launcher tells you).
setlocal
cd /d "%~dp0\.."
where py >nul 2>nul && (py -3 scripts\launch_offline_gui.py %* & goto :eof)
where python >nul 2>nul && (python scripts\launch_offline_gui.py %* & goto :eof)
echo Python 3.8+ was not found on PATH. Install it from https://www.python.org/ and retry.
pause
