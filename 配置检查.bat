@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ==========================================
echo   自动信息检索模块 — 环境检查与配置
echo ==========================================
echo.

:: 获取项目根目录（batch文件所在目录，自动便携）
set PROJECT_ROOT=%~dp0
set PROJECT_ROOT=%PROJECT_ROOT:~0,-1%

:: 检查 Node.js
echo [1/4] 检查 Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] 未找到 Node.js
    echo   请前往 https://nodejs.org 下载安装
    echo.
    pause
    exit /b 1
)
for /f "delims=" %%v in ('node --version') do set NODE_VER=%%v
echo   [OK] Node.js %NODE_VER%

:: 检查 npm
echo.
echo [2/4] 检查 npm...
npm --version >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] 未找到 npm
    echo.
    pause
    exit /b 1
)
for /f "delims=" %%v in ('npm --version') do set NPM_VER=%%v
echo   [OK] npm %NPM_VER%

:: 检查 Python（可选）
echo.
echo [3/4] 检查 Python（生成 Word 文档用）...
python --version >nul 2>&1
if errorlevel 1 (
    echo   [WARN] 未找到 Python（跳过 python-docx 依赖）
    echo   如需生成 docx 文件，请安装 Python 3.7+
    echo   并运行: pip install python-docx
    goto :skip_python
)
for /f "delims=" %%v in ('python --version') do set PY_VER=%%v
echo   [OK] Python %PY_VER%

:: 检查 python-docx
python -c "import docx" >nul 2>&1
if errorlevel 1 (
    echo   正在安装 python-docx...
    pip install python-docx -q
    if errorlevel 1 (
        echo   [WARN] python-docx 安装失败
        echo   可稍后手动运行: pip install python-docx
    ) else (
        echo   [OK] python-docx 安装成功
    )
) else (
    echo   [OK] python-docx 已安装
)

:skip_python

:: 检查浏览器服务（ skills-nju-browser 目录）
echo.
echo [4/4] 检查浏览器服务...

:: 优先使用环境变量，其次使用默认路径
if defined NJU_BROWSER_SKILLS (
    set SKILLS_DIR=%NJU_BROWSER_SKILLS%
    echo   [OK] 使用环境变量: %NJU_BROWSER_SKILLS%
) else (
    set SKILLS_DIR=%USERPROFILE%\AppData\Roaming\CherryStudio\Data\Skills\skills-nju-browser
)
if exist "%SKILLS_DIR%\nju-browser-server.js" (
    echo   [OK] 浏览器服务已找到
    echo   路径: !SKILLS_DIR!
) else (
    echo   [WARN] 未找到浏览器服务
    echo.
    echo   浏览器服务是搜索功能的必要依赖。
    echo   请在 Claude Code 中安装 skills-nju-browser skill，
    echo   或手动配置 NJU_BROWSER_SKILLS 环境变量指向包含
    echo   nju-browser-server.js 的目录。
    echo.
    echo   提示：站点爬取功能不需要浏览器服务，可独立使用
)

echo.
echo ==========================================
echo   环境检查完成
echo ==========================================
echo.
echo 项目路径: %PROJECT_ROOT%
echo.
echo === 环境变量配置（重要） ===
echo.
echo 搜索功能需要配置以下环境变量（永久设置需要在系统环境变量中添加）：
echo.
echo   Windows 用户（当前窗口临时生效）：
echo      set NJU_BROWSER_SKILLS=^(您的skills目录^)
echo.
echo   Linux/macOS 用户：
echo      export NJU_BROWSER_SKILLS=^(您的skills目录^)
echo.
echo   永久配置方法：
echo      Windows: 系统属性 - 环境变量 - 新建系统变量
echo      Linux: 在 ~/.bashrc 或 ~/.profile 中添加 export 语句
echo.
echo === 快速开始 ===
echo.
echo   1. 启动浏览器服务器（可选，仅搜索需要）：
echo      node "!SKILLS_DIR!\nju-browser-start.js"
echo.
echo   2. 启动 Agent 交互模式：
echo      cd /d "!PROJECT_ROOT!"
echo      node src\agent\index.js
echo.
echo   3. 查看帮助：
echo      cd /d "!PROJECT_ROOT!"
echo      node src\agent\index.js
echo      （输入 "帮助" 查看功能）
echo.
echo === 常用命令（所有命令在项目根目录执行）===
echo.
echo   node src\agent\index.js                      启动 Agent 交互
echo   node src\collector-generic.js --all           爬取全部站点
echo   node src\collector-generic.js --url ^<URL^>   爬取单个页面
echo   python docs\generate_docx.py                  生成网页清单 docx
echo.
echo 数据目录: src\..\data\
echo.
pause
