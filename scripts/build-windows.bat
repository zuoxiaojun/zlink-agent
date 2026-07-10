@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ===========================================================================
:: build-windows.bat — ZLink Agent Windows 桌面应用打包脚本
::
:: 用法：
::   scripts\build-windows.bat             默认打包
::   scripts\build-windows.bat --no-frontend  跳过前端构建
::   scripts\build-windows.bat --debug      PyInstaller debug 模式
::   scripts\build-windows.bat --installer  生成 NSIS 安装包（需安装 NSIS）
::
:: 前置条件：
::   - Python >= 3.11
::   - Node.js >= 18 + npm
::   - pip install pyinstaller
::   - （可选）NSIS 3.0+ — 用于生成安装包
:: ===========================================================================

set PROJECT_DIR=%~dp0..
cd /d "%PROJECT_DIR%"

set BUILD_FRONTEND=1
set DEBUG_MODE=
set BUILD_INSTALLER=

:parse_args
if "%~1"=="" goto :args_done
if "%~1"=="--no-frontend" set BUILD_FRONTEND=0
if "%~1"=="--debug" set DEBUG_MODE=--debug
if "%~1"=="--installer" set BUILD_INSTALLER=1
if "%~1"=="--help" goto :show_help
shift
goto :parse_args
:args_done

echo ========================================
echo   ZLink Agent Windows 打包脚本
echo ========================================
echo.

:: ── 1. 检查依赖 ──────────────────────────────────────────────────────────
echo [1/5] 检查依赖...

:: 找 Python
set PY_CMD=python
where python >nul 2>nul
if errorlevel 1 (
  where py >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] 需要 Python ^>= 3.11，请安装 https://www.python.org/downloads/
    pause
    exit /b 1
  )
  set PY_CMD=py
)

%PY_CMD% --version

:: 检查 PyInstaller
%PY_CMD% -c "import PyInstaller" 2>nul
if errorlevel 1 (
  echo [ERROR] 需要 PyInstaller，请运行: pip install pyinstaller
  pause
  exit /b 1
)

for /f "tokens=*" %%i in ('%PY_CMD% -c "import PyInstaller; print(PyInstaller.__version__)"') do set PYI_VER=%%i
echo   PyInstaller: %PYI_VER%

:: 检查 Node.js
where node >nul 2>nul
if errorlevel 1 (
  echo [WARN] Node.js 未安装 — 将使用已有 web/dist/
) else (
  for /f "tokens=*" %%i in ('node --version') do echo   Node.js: %%i
)

echo.

:: ── 2. 构建前端 ──────────────────────────────────────────────────────────
if "%BUILD_FRONTEND%"=="1" (
  echo [2/5] 构建前端...

  if not exist "web\node_modules" (
    echo   安装前端依赖...
    cd web
    call npm install --silent
    cd "%PROJECT_DIR%"
  )

  cd web
  call npm run build
  cd "%PROJECT_DIR%"
  echo [OK] 前端构建完成: web/dist/
) else (
  echo [2/5] 跳过前端构建（--no-frontend）
)

if not exist "web\dist" (
  echo [ERROR] web/dist/ 不存在！请先构建前端或去掉 --no-frontend
  pause
  exit /b 1
)
echo.

:: ── 3. 激活虚拟环境 ──────────────────────────────────────────────────────
echo [3/5] 准备 Python 环境...
if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
  echo [OK] 虚拟环境已激活: .venv
) else if exist ".venv\Scripts\activate" (
  call ".venv\Scripts\activate"
  echo [OK] 虚拟环境已激活: .venv
) else (
  echo [WARN] 未找到 .venv，使用系统 Python 环境
)
echo.

:: ── 4. 预缓存 MCP 依赖 ──────────────────────────────────────────────────
echo [4/5] 预缓存 MCP 依赖...

where npx >nul 2>nul
if not errorlevel 1 (
  echo   缓存 mcp-server-chart (npx)...
  call npx -y @antv/mcp-server-chart --version >nul 2>nul
  if errorlevel 1 (
    echo   [WARN] mcp-server-chart 缓存失败（不影响构建）
  ) else (
    echo   [OK] mcp-server-chart 已缓存
  )
) else (
  echo   [WARN] npx 未安装，跳过缓存
)
echo.

:: ── 5. 运行 PyInstaller ──────────────────────────────────────────────────
echo [5/5] 运行 PyInstaller 打包...

:: 清理之前的构建
if exist "dist\ZLink-Agent" rmdir /s /q "dist\ZLink-Agent"
if exist "build" rmdir /s /q "build"

set PYTHONPATH=
%PY_CMD% -m PyInstaller packaging\zlink-agent.spec --clean --noconfirm %DEBUG_MODE%

echo.

:: ── 完成 ────────────────────────────────────────────────────────────────
if exist "dist\ZLink-Agent\zlink-agent.exe" (
  for /f "tokens=*" %%i in ('powershell -command "(Get-Item 'dist\ZLink-Agent').Length"') do set APP_SIZE=%%i
  for /f "tokens=*" %%i in ('powershell -command "$p = Get-ChildItem 'dist\ZLink-Agent' -Recurse | Measure-Object -Property Length -Sum; $p.Sum"') do set APP_BYTES=%%i

  :: ── 生成 Windows 启动脚本 ─────────────────────────────────────────
  echo [^+] 生成 Windows 启动脚本...
  (
    echo @echo off
    echo chcp 65001 >nul
    echo cd /d "%%~dp0"
    echo echo ========================================
    echo echo   ZLink Agent 启动中...
    echo echo   访问地址: http://127.0.0.1:8089
    echo echo   按 Ctrl+C 停止服务
    echo echo ========================================
    echo echo.
    echo start "" http://127.0.0.1:8089
    echo zlink-agent.exe
    pause
  ) > "dist\ZLink-Agent\start-zlink-agent.bat"

  echo.
  echo ========================================
  echo   ✅ ZLink Agent Windows 打包完成
  echo ========================================
  echo   输出: dist\ZLink-Agent\
  echo   入口: dist\ZLink-Agent\zlink-agent.exe
  echo   双击: dist\ZLink-Agent\start-zlink-agent.bat
  echo.
  echo   数据目录: %%USERPROFILE%%\.zlink-agent\data\
  echo ========================================

  :: ── NSIS 安装包 ─────────────────────────────────────────────────
  if "%BUILD_INSTALLER%"=="1" (
    echo.
    echo [^+] 生成 NSIS 安装包...

    where makensis >nul 2>nul
    if not errorlevel 1 (
      makesis packaging\installer.nsi
      if errorlevel 1 (
        echo [ERROR] NSIS 构建失败
      ) else (
        echo [OK] 安装包已生成
      )
    ) else (
      echo [WARN] makensis 未找到，跳过安装包生成
    )
  )

) else (
  echo [ERROR] 打包失败 — dist\ZLink-Agent\zlink-agent.exe 未生成
  pause
  exit /b 1
)

echo.
pause
goto :eof

:show_help
echo 用法: scripts\build-windows.bat [选项]
echo.
echo 选项:
echo   --no-frontend    跳过前端构建（如果 web/dist/ 已经存在）
echo   --debug          PyInstaller debug 模式（生成更多日志）
echo   --installer      额外生成 NSIS 安装包（需安装 NSIS）
echo   --help           显示此帮助
pause
goto :eof