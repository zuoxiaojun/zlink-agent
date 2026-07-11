@echo off
chcp 65001 >nul
:: ===========================================================================
:: setup.bat — ZLink Agent Windows 一键安装部署脚本
::
:: 前置条件：
::   - Python >= 3.11
::   - Node.js >= 18 + npm
::   - git（可选，用于升级功能）
::
:: 环境变量：
::   ZLINK_AUTO_INSTALL=1      自动安装缺失依赖（使用 winget / chocolatey）
::   ZLINK_USE_MIRROR=true      是否使用国内镜像（默认 true）
::   ZLINK_PIP_MIRROR=...       PyPI 镜像地址
::   ZLINK_NPM_MIRROR=...       npm 镜像地址
:: ===========================================================================

setlocal enabledelayedexpansion

set PROJECT_DIR=%~dp0
set PROJECT_DIR=%PROJECT_DIR:~0,-1%

echo ========================================
echo   ZLink Agent Windows 安装部署
echo   %PROJECT_DIR%
echo ========================================
echo.

:: ── 检测是否已有安装 ──
set IS_UPGRADE=false
if exist ".venv\Scripts\python.exe" set IS_UPGRADE=true
if "%IS_UPGRADE%"=="true" (
  echo [INFO] 检测到已有安装，升级模式，用户 data/ 目录会保留
  echo.
)

:: ── 确认安装辅助 ──
set _AUTO_INSTALL=%ZLINK_AUTO_INSTALL%
if "%_AUTO_INSTALL%"=="" set _AUTO_INSTALL=0

:: =====================================================================
:: 1. 依赖检查 + 自动安装
:: =====================================================================
echo [1/8] 检查依赖环境...

:: ── 1a. 找 Python >= 3.11 ──
set PY_CMD=
for %%v in (python3.12 python3.11 python3 python) do (
  where %%v >nul 2>nul
  if not errorlevel 1 (
    set PY_CMD=%%v
    goto :found_py
  )
)
:found_py
if "%PY_CMD%"=="" (
  echo [WARN] 需要 Python ^>= 3.11
  if "%_AUTO_INSTALL%"=="1" (
    where winget >nul 2>nul
    if not errorlevel 1 (
      echo   尝试 winget 安装 Python 3.12...
      winget install Python.Python.3.12 --accept-package-agreements
      if not errorlevel 1 (
        set PY_CMD=python
        echo [OK] Python 3.12 已安装
        goto :py_done
      )
    )
    where choco >nul 2>nul
    if not errorlevel 1 (
      echo   尝试 chocolatey 安装 Python...
      choco install python -y
      if not errorlevel 1 (
        set PY_CMD=python
        echo [OK] Python 已安装
        goto :py_done
      )
    )
    echo [ERROR] 自动安装失败，请手动安装 Python 3.11+
  )
  echo   请安装: https://www.python.org/downloads/
  pause
  exit /b 1
)
:py_done
for /f "tokens=*" %%i in ('%PY_CMD% --version 2^>^&1') do echo [OK] %%i

:: ── 1b. Node.js >= 18 ──
:check_node
where node >nul 2>nul
if errorlevel 1 (
  echo [WARN] 需要 Node.js ^>= 18
  if "%_AUTO_INSTALL%"=="1" (
    where winget >nul 2>nul
    if not errorlevel 1 (
      echo   尝试 winget 安装 Node.js LTS...
      winget install OpenJS.NodeJS.LTS --accept-package-agreements
      if not errorlevel 1 goto :check_node
    )
    where choco >nul 2>nul
    if not errorlevel 1 (
      echo   尝试 chocolatey 安装 Node.js...
      choco install nodejs -y
      if not errorlevel 1 goto :check_node
    )
  )
  echo [ERROR] 需要 Node.js ^>= 18
  echo   请安装: https://nodejs.org/
  pause
  exit /b 1
)

:: Node.js 版本检查
for /f "tokens=1 delims=v." %%i in ('node --version') do set NODE_MAJOR=%%i
if "%NODE_MAJOR%"=="" set NODE_MAJOR=0
if %NODE_MAJOR% LSS 18 (
  echo [ERROR] Node.js 版本过低 (v%NODE_MAJOR%)，需要 ^>= 18
  echo   请升级: https://nodejs.org/
  pause
  exit /b 1
)
for /f "tokens=*" %%i in ('node --version') do echo [OK] Node.js: %%i

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] 需要 npm（通常随 Node.js 一起安装）
  pause
  exit /b 1
)
for /f "tokens=*" %%i in ('npm --version') do echo [OK] npm: %%i

where git >nul 2>nul
if errorlevel 1 (
  echo [WARN] 未找到 git，无法使用升级功能
) else (
  for /f "tokens=*" %%i in ('git --version') do echo [OK] %%i
)
echo.

:: =====================================================================
:: 2. 镜像配置
:: =====================================================================
echo [2/8] 配置镜像源...
set USE_MIRROR=%ZLINK_USE_MIRROR%
if "%USE_MIRROR%"=="" set USE_MIRROR=true

set NPM_MIRROR=%ZLINK_NPM_MIRROR%
if "%NPM_MIRROR%"=="" set NPM_MIRROR=https://mirrors.npmmirror.com

if "%USE_MIRROR%"=="true" (
  if defined ZLINK_PIP_MIRROR (
    set PIP_MIRROR=%ZLINK_PIP_MIRROR%
    echo   PIP: %PIP_MIRROR% ^(用户指定^)
  ) else (
    echo   PIP 镜像回退链:
    echo     - https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
    echo     - https://mirrors.aliyun.com/pypi/simple
    echo     - https://mirrors.cloud.tencent.com/pypi/simple
    echo     - https://pypi.org/simple
  )
  echo   NPM: %NPM_MIRROR% ^(--registry 临时切换^)
) else (
  echo   不使用镜像源
)
echo.

:: =====================================================================
:: 3. Python 虚拟环境
:: =====================================================================
echo [3/8] 创建 Python 虚拟环境...
if not exist ".venv\Scripts\python.exe" (
  %PY_CMD% -m venv .venv
  if errorlevel 1 (
    echo [ERROR] 虚拟环境创建失败
    echo   重装 Python 时勾选 "tcl/tk and IDLE" 和 "Add to PATH"
    pause
    exit /b 1
  )
  echo [OK] 虚拟环境已创建
) else (
  echo [INFO] 虚拟环境已存在，跳过
)
".venv\Scripts\python.exe" -m pip --version >nul 2>nul
if errorlevel 1 (
  echo [ERROR] pip 不可用
  echo   运行: python -m ensurepip --upgrade
  pause
  exit /b 1
)
echo [OK] venv pip 就绪
echo.

:: =====================================================================
:: 4. 安装 Python 依赖
:: =====================================================================
echo [4/8] 安装 Python 依赖...
call .venv\Scripts\activate.bat

echo   升级 pip...
call :pip_install_robust --upgrade pip || echo [WARN] pip 升级失败

echo   安装项目依赖...
call :pip_install_robust -r requirements.txt
if errorlevel 1 (
  echo [ERROR] 依赖安装失败
  pause
  exit /b 1
)

echo   验证依赖...
pip check >nul 2>nul
if errorlevel 1 (echo [WARN] 依赖冲突) else (echo [OK] 依赖一致)
echo [OK] Python 依赖安装完成
echo.

:: pip 安装辅助（镜像回退，输出不隐藏）
:pip_install_robust
if "%USE_MIRROR%"=="true" (
  if defined PIP_MIRROR (
    echo     尝试镜像: %PIP_MIRROR%
    pip install --retries 1 --timeout 15 -i "%PIP_MIRROR%" %*
    if not errorlevel 1 exit /b 0
    echo     [WARN] 镜像失败
    exit /b 1
  ) else (
    for %%m in (
      "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple"
      "https://mirrors.aliyun.com/pypi/simple"
      "https://mirrors.cloud.tencent.com/pypi/simple"
      "https://pypi.org/simple"
    ) do (
      echo     尝试镜像: %%m
      pip install --retries 1 --timeout 15 -i %%m %*
      if not errorlevel 1 (
        echo     [OK] 安装成功
        exit /b 0
      )
      echo     [WARN] 失败，尝试下一个...
    )
    echo [ERROR] 所有镜像均不可用
    exit /b 1
  )
) else (
  pip install --retries 1 --timeout 15 %*
  if not errorlevel 1 exit /b 0
  echo [ERROR] PyPI 安装失败
  exit /b 1
)

:: =====================================================================
:: 5. 配置文件
:: =====================================================================
echo [5/8] 配置文件...
if not exist ".env" (
  if exist ".env.example" (
    copy ".env.example" ".env" >nul
    echo [OK] .env 已创建
  ) else (
    echo [WARN] .env.example 不存在
  )
) else (
  echo [INFO] .env 已存在
)
echo.

:: =====================================================================
:: 6. 数据目录 (运行时路径 ~/.zlink-agent/data/)
:: =====================================================================
echo [6/8] 创建数据目录...
if not exist "%USERPROFILE%\.zlink-agent\data" mkdir "%USERPROFILE%\.zlink-agent\data"
if not exist "%USERPROFILE%\.zlink-agent\data\logs" mkdir "%USERPROFILE%\.zlink-agent\data\logs"
if not exist "%USERPROFILE%\.zlink-agent\data\sessions" mkdir "%USERPROFILE%\.zlink-agent\data\sessions"
if not exist "%USERPROFILE%\.zlink-agent\data\memory" mkdir "%USERPROFILE%\.zlink-agent\data\memory"
if not exist "%USERPROFILE%\.zlink-agent\data\backups" mkdir "%USERPROFILE%\.zlink-agent\data\backups"
echo [OK] %USERPROFILE%\.zlink-agent\data\
echo.

:: =====================================================================
:: 7. 前端构建
:: =====================================================================
echo [7/8] 安装前端依赖并构建...
cd web

set NPM_FLAGS=
if "%USE_MIRROR%"=="true" (
  set NPM_FLAGS=--registry %NPM_MIRROR%
  echo [INFO] npm 镜像: %NPM_MIRROR% ^(--registry 临时切换^)
)

call npm %NPM_FLAGS% install
if errorlevel 1 (
  echo [ERROR] 前端依赖安装失败
  cd "%PROJECT_DIR%"
  pause
  exit /b 1
)
echo [OK] 前端依赖安装完成

call npm %NPM_FLAGS% run build
if errorlevel 1 (
  echo [ERROR] 前端构建失败
  cd "%PROJECT_DIR%"
  pause
  exit /b 1
)
echo [OK] 前端构建完成
cd "%PROJECT_DIR%"
echo.

:: =====================================================================
:: 8. 快捷命令 + 数据迁移
:: =====================================================================
echo [8/8] 安装快捷命令并执行初始化...

set INSTALL_DIR=%USERPROFILE%\.local\bin
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
copy "scripts\zlink.sh" "%INSTALL_DIR%\zlink" >nul 2>&1
echo [OK] 快捷命令: %INSTALL_DIR%

echo %PATH% | findstr /i "%INSTALL_DIR%" >nul
if errorlevel 1 (
  echo [WARN] %%USERPROFILE%%\.local\bin 不在 PATH 中，请手动添加
)

call .venv\Scripts\activate.bat
set PYTHONPATH=%PROJECT_DIR%
python -m scripts.migrate
if errorlevel 1 (echo [WARN] 数据迁移异常) else (echo [OK] 数据迁移完成)

:: ── 完成 ──
echo.
echo ========================================
if "%IS_UPGRADE%"=="true" (
  echo   ✅ ZLink Agent 升级完成
) else (
  echo   ✅ ZLink Agent 安装完成
)
echo ========================================
echo.
echo   安装路径: %PROJECT_DIR%
if "%IS_UPGRADE%"=="true" (
  echo   用户数据: 已保留
) else (
  echo   数据目录: %USERPROFILE%\.zlink-agent\data\
)
echo.
echo   启动方式:
echo     start.bat             生产模式启动
echo     start.bat --dev       开发模式
echo     start.bat stop        停止服务
echo.
echo ========================================
pause
