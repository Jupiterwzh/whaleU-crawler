@echo off
chcp 65001 >/dev/null
cd /d "%~dp0browser"
echo.
echo ==========================================
echo   NJU Browser Server - Starting...
echo ==========================================
echo.
node nju-browser-server.js
