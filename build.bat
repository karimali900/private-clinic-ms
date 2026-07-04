@echo off
REM =====================================================
REM  Build OMS — Obstetrics Management System
REM  Created by Karim Abdelaziz — 00201029927276
REM =====================================================
title Building OMS Package...

set DIR=%~dp0
cd /d "%DIR%"

echo.
echo ^>^> Installing build dependencies...
pip install pyinstaller

echo.
echo ^>^> Installing required Python packages...
pip install fastapi uvicorn passlib python-jose pydantic websockets python-multipart scikit-learn pandas numpy

echo.
echo ^>^> Building executable with PyInstaller...
pyinstaller --clean --noconfirm --onefile --windowed ^
  --name "OMS" ^
  --add-data "data;data" ^
  --hidden-import passlib.handlers.pbkdf2_sha256 ^
  --hidden-import passlib.handlers.sha2_crypt ^
  --hidden-import uvicorn ^
  --hidden-import uvicorn.logging ^
  --hidden-import uvicorn.loops.auto ^
  --hidden-import uvicorn.protocols.http.auto ^
  --hidden-import uvicorn.protocols.websockets.auto ^
  --hidden-import uvicorn.middleware.asgi2 ^
  --hidden-import uvicorn.middleware.wsgi ^
  --hidden-import uvicorn.lifespan.on ^
  --hidden-import fastapi ^
  --hidden-import pydantic ^
  --hidden-import starlette.middleware.cors ^
  --hidden-import websockets ^
  --hidden-import websockets.legacy.client ^
  --hidden-import websockets.legacy.server ^
  --hidden-import httptools ^
  --hidden-import database ^
  --hidden-import multipart ^
  --hidden-import multipart.multipart ^
  --hidden-import sklearn ^
  --hidden-import sklearn.ensemble ^
  --hidden-import sklearn.tree ^
  --hidden-import sklearn.preprocessing ^
  --hidden-import pandas ^
  --hidden-import numpy ^
  --exclude-module tkinter ^
  --exclude-module matplotlib ^
  --exclude-module scipy ^
  --exclude-module PIL ^
  run.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ====================================================
    echo  BUILD FAILED!
    echo  Check the error messages above.
    echo ====================================================
    echo.
    echo  Common Windows fixes:
    echo   1. Install Python from python.org (not Microsoft Store)
    echo   2. Check "Add Python to PATH" during install
    echo   3. Run Command Prompt as Administrator
    echo   4. If numpy fails: pip install numpy --prefer-binary
    echo.
    pause
    exit /b 1
)

echo.
echo ^>^> Copying data files...
if not exist "dist\data" mkdir "dist\data"
xcopy /E /I /Y "data" "dist\data"
copy "start.bat" "dist\start.bat"
copy "README.txt" "dist\README.txt"

echo.
echo ====================================================
echo  BUILD COMPLETE!
echo  Output: dist\OMS.exe
echo  Size:
dir "dist\OMS.exe"
echo ====================================================
echo.
echo  Created by Karim Abdelaziz
echo  00201029927276
echo.
pause
