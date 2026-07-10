@echo off
chcp 65001 >nul
:: ===========================================================================
:: start.bat — ZLink Agent Windows 启动入口
::
:: 用法：
::   start.bat           启动（默认生产模式，Serve 前端）
::   start.bat --dev     启动（开发模式，Vite 热更新）
::   start.bat stop      停止
::   start.bat --help    帮助
:: ===========================================================================

setlocal enabledelayedexpansion

set CMD=%1

if "%CMD%"=="--help" goto :show_help
if "%CMD%"=="stop" goto :stop_server
if "%CMD%"=="--dev" goto :dev_mode

:: ── 生产模式 ──────────────────────────────────────────────────────────────
:prod_mode
echo ========================================
echo   ZLink Agent — 生产模式
echo ========================================

:: 检查虚拟环境
if exist ".venv\Scripts\activate" (
    call .venv\Scripts\activate
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

:: 检查依赖
pip show uvicorn >nul 2>&1
if errorlevel 1 (
    echo [INFO] 安装依赖...
    pip install -r requirements.txt
)

:: 构建前端
if not exist "web\dist\index.html" (
    echo [INFO] 构建前端...
    cd web
    call npm install
    call npm run build
    cd ..
)

:: 启动后端（Serve 前端静态文件）
echo.
echo 启动服务: http://127.0.0.1:8089
echo 按 Ctrl+C 停止服务
echo.

python -m backend
goto :eof

:: ── 开发模式 ──────────────────────────────────────────────────────────────
:dev_mode
echo ========================================
echo   ZLink Agent — 开发模式（Vite 热更新）
echo ========================================

:: 检查虚拟环境
if exist ".venv\Scripts\activate" (
    call .venv\Scripts\activate
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

:: 检查依赖
pip show uvicorn >nul 2>&1
if errorlevel 1 (
    echo [INFO] 安装依赖...
    pip install -r requirements.txt
)

cd web
if not exist "node_modules" call npm install

:: 启动 Vite 前端（后台窗口）
echo 启动 Vite 开发服务器（端口 8088）...
start "ZLink Agent Vite" cmd /c "npx vite --port 8088 --host"
cd ..

:: 启动后端
echo.
echo 启动后端服务: http://127.0.0.1:8089
echo 前端开发: http://127.0.0.1:8088
echo 按 Ctrl+C 停止服务
echo.

python -m backend
goto :eof

:: ── 停止服务 ──────────────────────────────────────────────────────────────
:stop_server
echo 停止 ZLink Agent 服务...
for /f "tokens=2" %%a in ('tasklist /fi "imagename eq python.exe" /nh ^| findstr /i "backend"') do (
    taskkill /f /pid %%a >nul 2>&1
)
for /f "tokens=2" %%a in ('tasklist /fi "imagename eq node.exe" /nh ^| findstr /i "vite"') do (
    taskkill /f /pid %%a >nul 2>&1
)
echo [OK] 服务已停止
goto :eof

:: ── 帮助 ──────────────────────────────────────────────────────────────────
:show_help
echo 用法: start.bat [选项]
echo.
echo 选项:
echo   （无参数）    生产模式 — 后端 Serve 前端
echo   --dev         开发模式 — 后端 + Vite 热更新
echo   stop          停止服务
echo   --help        显示此帮助
goto :eof