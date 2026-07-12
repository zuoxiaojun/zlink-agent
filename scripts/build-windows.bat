@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ===========================================================================
:: build-windows.bat — ZLink Agent Windows 桌面应用打包脚本
::
:: 使用 Electron + electron-builder 打包 Windows .exe
:: 参考 scripts/build-electron.sh（macOS/Linux 版）
::
:: 用法：
::   scripts\build-windows.bat             默认打包（前端构建 + Python bundle + 打包）
::   scripts\build-windows.bat --no-frontend  跳过前端构建
::   scripts\build-windows.bat --no-bundle    跳过 Python bundle（使用现有 .venv）
::   scripts\build-windows.bat --help         显示帮助
::
:: 前置条件：
::   - Node.js >= 18 + npm
::   - Python >= 3.11
::   - pip install -r requirements.txt
::   - Git Bash（用于 bundle-python.sh）
:: ===========================================================================

set PROJECT_DIR=%~dp0..
cd /d "%PROJECT_DIR%"

set BUILD_FRONTEND=1
set SKIP_BUNDLE=

:parse_args
if "%~1"=="" goto :args_done
if "%~1"=="--no-frontend" set BUILD_FRONTEND=0
if "%~1"=="--no-bundle" set SKIP_BUNDLE=1
if "%~1"=="--help" goto :show_help
shift
goto :parse_args
:args_done

echo ========================================
echo   ZLink Agent Windows 打包脚本
echo   使用 Electron 构建
echo ========================================
echo.

:: ── 1. 检查依赖 ──────────────────────────────────────────────────────────
echo [1/5] 检查依赖...

where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] 需要 Node.js ^>= 18，请安装 https://nodejs.org/
  pause
  exit /b 1
)
for /f "tokens=*" %%i in ('node --version') do echo   Node.js: %%i

:: 检查 npx（electron-builder 通过 npx 调用）
where npx >nul 2>nul
if errorlevel 1 (
  echo [ERROR] 需要 npm/npx，请安装 Node.js
  pause
  exit /b 1
)

:: ── 检查 Git Bash（bundle-python.sh 需要）─────────────────────────────
where bash >nul 2>nul
if errorlevel 1 (
  echo [WARN] Git Bash 未找到 — Python bundle 需要 bash 环境
  echo   Windows 请安装 Git for Windows: https://git-scm.com/download/win
  echo   或使用 --no-bundle 跳过 Python bundle 步骤
)

echo.

:: ── 2. 构建前端 ──────────────────────────────────────────────────────────
if "%BUILD_FRONTEND%"=="1" (
  echo [2/5] 构建前端...

  pushd web
  if not exist "node_modules" (
    echo   安装前端依赖...
    call npm install --silent
  )
  call npm run build
  popd
  echo [OK] 前端构建完成: web/dist/
) else (
  echo [2/5] 跳过前端构建（--no-frontend）
)

if not exist "web\dist\index.html" (
  echo [ERROR] web/dist/index.html 不存在！请先构建前端
  pause
  exit /b 1
)
echo.

:: ── 3. 打包 Python 运行环境 ─────────────────────────────────────────────
if "%SKIP_BUNDLE%"=="1" (
  echo [3/5] 跳过 Python bundle（--no-bundle）
  echo   注意：electron-builder 需要 build/python-bundle/ 目录
  echo   请确保已手动运行: bash scripts/bundle-python.sh
) else (
  echo [3/5] 打包 Python 运行环境...
  where bash >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] 需要 Git Bash 运行 bundle-python.sh
    echo   请安装 Git for Windows 后重试，或使用 --no-bundle
    pause
    exit /b 1
  )
  bash scripts/bundle-python.sh
  if errorlevel 1 (
    echo [ERROR] Python bundle 打包失败
    pause
    exit /b 1
  )
  echo [OK] Python bundle 完成: build/python-bundle/
)
echo.

:: ── 4. 预缓存 MCP 依赖 ──────────────────────────────────────────────────
echo [4/5] 预缓存 MCP 依赖...

call npx -y @antv/mcp-server-chart --version >nul 2>nul
if errorlevel 1 (
  echo   [WARN] mcp-server-chart 缓存失败（不影响构建）
) else (
  echo   [OK] mcp-server-chart 已缓存
)
echo.

:: ── 5. 运行 electron-builder ────────────────────────────────────────────
echo [5/5] 运行 electron-builder 打包 Windows 应用...

:: 清理之前的构建
if exist "dist-electron" (
  echo   清理 dist-electron/...
  rmdir /s /q "dist-electron"
)

call npx electron-builder --win --config electron-builder.yml
if errorlevel 1 (
  echo [ERROR] Electron 打包失败
  pause
  exit /b 1
)
echo.

:: ── 完成 ────────────────────────────────────────────────────────────────
:: 清理 .blockmap 和中间产物
if exist "dist-electron\*.blockmap" del /q "dist-electron\*.blockmap"
if exist "dist-electron\builder-debug.yml" del /q "dist-electron\builder-debug.yml"
if exist "dist-electron\mac" rmdir /s /q "dist-electron\mac"
if exist "dist-electron\mac-arm64" rmdir /s /q "dist-electron\mac-arm64"
if exist "dist-electron\win-unpacked" rmdir /s /q "dist-electron\win-unpacked"

echo.
echo ========================================
echo   ✅ ZLink Agent Windows 打包完成
echo ========================================
echo   输出目录:
dir "dist-electron" /b 2>nul
echo.
echo   安装: 双击 dist-electron\ 下的 ZLink Agent Setup 安装包
echo   数据目录: %%USERPROFILE%%\.zlink-agent\data\
echo ========================================
echo.
pause
goto :eof

:show_help
echo 用法: scripts\build-windows.bat [选项]
echo.
echo 选项:
echo   --no-frontend    跳过前端构建（如果 web/dist/ 已存在）
echo   --no-bundle      跳过 Python bundle（用 --no-venv 跑 bundle-python.sh）
echo   --help           显示此帮助
echo.
echo 示例:
echo   scripts\build-windows.bat              完整构建
echo   scripts\build-windows.bat --no-frontend  跳过前端（仅打包）
echo.
pause
goto :eof