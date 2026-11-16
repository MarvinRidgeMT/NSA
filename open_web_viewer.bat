@echo off
REM Open the POLARIS X web viewer on Windows: double-click this file. Needs Python 3 (python.org or the Microsoft Store).
REM Serves web\dist on http://127.0.0.1:8765 and opens the default browser. Close this window to stop it.
cd /d "%~dp0web\dist" || (echo web\dist is missing & pause & exit /b 1)
if not exist index.html (echo web\dist\index.html is missing & pause & exit /b 1)
start "" "http://127.0.0.1:8765/"
where py >nul 2>nul && (py -3 -m http.server 8765 --bind 127.0.0.1) || (python -m http.server 8765 --bind 127.0.0.1)
pause
