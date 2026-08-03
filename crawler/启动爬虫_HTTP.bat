@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ==========================================
echo   Blue Whale U - HTTP Mode Crawler
echo ==========================================
echo.
echo Usage:
echo   node src\collectors\collector.js --site ^<URL^>       Crawl site
echo   node src\collectors\collector.js --notices ^<URL^>    Crawl notice list
echo   node src\collectors\collector.js --url ^<URL^>        Crawl single page
echo.
echo Examples:
echo   node src\collectors\collector.js --site https://cs.nju.edu.cn/ --max-pages 1
echo   node src\collectors\collector.js --notices https://cs.nju.edu.cn/1702/list.htm
echo.
pause
