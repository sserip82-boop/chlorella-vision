@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3.11 -m venv .venv
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -c "import streamlit, cv2, streamlit_image_coordinates, pandas, PIL" >nul 2>&1
if errorlevel 1 (
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" scripts\start_app.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo Could not start. Check Python 3.11 and the error message above.
pause
exit /b 1
