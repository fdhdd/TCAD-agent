@echo off
set PATH=C:\Program Files\nodejs;%PATH%
echo Starting TCAD Agent...

echo Starting backend server...
start "TCAD Backend" cmd /k "cd c:\Users\Administrator\Desktop\TCAD agent && npx tsx api/index.ts"

timeout /t 3 /nobreak >nul

echo Starting frontend server...
start "TCAD Frontend" cmd /k "cd c:\Users\Administrator\Desktop\TCAD agent && npx vite"

echo Services are starting...
echo Backend: http://localhost:3001
echo Frontend: http://localhost:3000