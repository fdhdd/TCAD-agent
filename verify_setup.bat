@echo off
echo ==========================================
echo   TCAD Agent Repository Verification
echo ==========================================
echo.

cd "c:\Users\Administrator\Desktop\TCAD agent"

echo Checking local repository status...
git status
echo.

echo Checking remote repositories...
git remote -v
echo.

echo Checking branches...
git branch -a
echo.

echo Checking recent commits...
git log --oneline -5
echo.

echo ==========================================
echo Verification Complete!
echo ==========================================
echo.
echo If you see your commits and both master/develop branches,
echo your repository is properly set up.
echo.
echo Visit: https://github.com/fdhdd/TCAD-agent
echo.

pause