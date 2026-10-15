@echo off
cd /d "%~dp0"

echo ==============================================
echo   Aviation Briefing - starting server...
echo ==============================================
echo   Address: http://localhost:8080
echo   The browser will open automatically.
echo   Press Ctrl+C to stop the server.
echo ==============================================
echo.

py -3 -c "import sys" >nul 2>nul
if "%errorlevel%"=="0" goto run_py
python -c "import sys" >nul 2>nul
if "%errorlevel%"=="0" goto run_python
python3 -c "import sys" >nul 2>nul
if "%errorlevel%"=="0" goto run_python3

echo.
echo   [ERROR] Python was not found.
echo   Install it from https://www.python.org/downloads/
echo   IMPORTANT: tick "Add Python to PATH" during setup.
echo   Then double-click this file again.
echo.
pause
exit /b 1

:run_py
echo   Using: py -3
py -3 server.py
goto done

:run_python
echo   Using: python
python server.py
goto done

:run_python3
echo   Using: python3
python3 server.py
goto done

:done
echo.
echo   Server stopped.
pause
