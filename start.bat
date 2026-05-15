@echo off
set PATH=C:\Program Files\nodejs;%PATH%
echo Starting TCAD Agent...
start "TCAD Frontend" cmd /k "npm run dev:frontend"
timeout /t 2 /nobreak > nul
start "TCAD Backend" cmd /k "npm run dev:backend"
exit