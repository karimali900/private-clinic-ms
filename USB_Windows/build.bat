@echo off
REM =====================================================
REM  Build OMS — Obstetrics Management System Installer
REM  Created by Karim Abdelaziz — 00201029927276
REM =====================================================
title Building OMS Package...

set DIR=%~dp0
cd /d "%DIR%"

echo ^>^> Installing build dependencies...
pip install pyinstaller pyarmor pyarmor.cli 2>nul

echo.
echo ^>^> Obfuscating source code with PyArmor...
pyarmor gen --output obf_dist --recursive run.py Cloud_API.py database.py classification.py Postpartum.py maternal_fetal.py 2>nul

echo.
echo ^>^> Building executable with PyInstaller...
cd obf_dist
pyinstaller --clean --noconfirm --onefile --windowed ^
  --name "OMS" ^
  --add-data "../data;data" ^
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
  --exclude-module cv2 ^
  run.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Build failed. Check the output above.
    pause
    exit /b 1
)

echo.
echo ^>^> Copying files to dist folder...
cd "%DIR%"
if not exist "dist\data" mkdir "dist\data"
xcopy /E /I /Y "data" "dist\data" 2>nul
copy "start.bat" "dist\start.bat" 2>nul
copy "README.txt" "dist\README.txt" 2>nul

echo.
echo ====================================================
echo  BUILD COMPLETE!
echo  Output: dist\OMS.exe
echo ====================================================
echo.
echo  Created by Karim Abdelaziz
echo  00201029927276
echo.
pause
