@echo off
title Obstetrics Management System
echo ====================================================
echo   Obstetrics Management System
echo   Maternity Ward . Labor & Delivery . Postnatal Care
echo ====================================================
echo.
echo   created by Karim Abdelaziz — 00201029927276
echo.
echo   Starting server...
echo.
start "" "%~dp0OMS.exe"
echo   Opening browser...
timeout /t 2 /nobreak >nul
start http://localhost:5000/dashboard
exit
