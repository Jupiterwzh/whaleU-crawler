@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ==========================================
echo   Blue Whale U - NJU Notice Crawler
echo   HTTP Mode (default)
echo ==========================================
echo.
echo Usage:
echo   node src\collectors\collector.js --site ^<URL^>       Crawl site with strategy
echo   node src\collectors\collector.js --notices ^<URL^>    Crawl notice list
echo   node src\collectors\collector.js --url ^<URL^>        Crawl single page
echo   node src\collectors\collector.js --list-strategies    List all strategies
echo   node src\collectors\collector.js --stats              Show stats
echo   node src\collectors\collector.js --help               Show help
echo.
echo Data dir: %~dp0data\
echo.
node src\collectors\collector.js --list-strategies
echo.
echo To crawl a site:
echo   node src\collectors\collector.js --site https://cs.nju.edu.cn/ --max-pages 1
echo.
pause
