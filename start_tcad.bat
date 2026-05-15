@echo off
cd /d C:\Users\Administrator\Desktop\TCAD agent
set PATH=C:\Program Files\nodejs;%PATH%
start "TCAD Backend" cmd /k "npx tsx api/index.ts"
timeout /t 2 >nul
start "TCAD Frontend" cmd /k "npx vite"
