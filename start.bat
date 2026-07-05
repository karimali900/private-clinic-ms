@echo off
title Obstetrics Management System
echo ====================================================
echo   Obstetrics Management System
echo   Maternity Ward . Labor & Delivery . Postnatal Care
echo ====================================================
echo.
echo   Created by Karim Abdelaziz — 00201029927276
echo.
cd /d "%~dp0"

REM Run compiled binary if present
if exist "%~dp0OMS.exe" (
    echo   Starting...
    start "" "%~dp0OMS.exe"
    timeout /t 2 /nobreak >nul
    start http://localhost:5000/dashboard
    exit
)

REM Source mode
echo   Starting Python server...
start "" python run.py
timeout /t 3 /nobreak >nul
start http://localhost:5000/dashboard
