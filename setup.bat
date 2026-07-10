@echo off
chcp 65001 >nul
:: ===========================================================================
:: setup.bat — ZLink Agent Windows 一键安装部署脚本
::
:: 前置条件：
::   - Python >= 3.11（https://www.python.org/downloads/）
::   - Node.js >= 18 + npm（https://nodejs.org/）
::   - git（可选，用于升级功能）
::
:: 功能：
::   1. 检查依赖环境
::   2. 创建 Python 虚拟环境
::   3. 安装 Python 依赖（支持国内镜像加速）
::   4. 创建 .env 配置文件
::   5. 创建数据目录
::   6. 构建前端
::   7. 安装快捷命令
::   8. 执行数据迁移
::
:: 环境变量（镜像加速）：
::   YS_USE_MIRROR=true          是否使用国内镜像（默认 true）
::   YS_PIP_MIRROR=...           PyPI 镜像地址
::   YS_NPM_MIRROR=...           npm 镜像地址
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
  echo [INFO] 检测到已有安装，升级模式
  echo [INFO] 用户 data/ 目录会保留
  echo.
)

:: ── 1. 依赖检查 ─────────────────────────────────────────────────────────
echo [1/8] 检查依赖环境...

:: 找 Python
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
  echo [ERROR] 需要 Python ^>= 3.11，未找到。
  echo   请安装: https://www.python.org/downloads/
  pause
  exit /b 1
)

for /f "tokens=*" %%i in ('%PY_CMD% --version 2^>^&1') do echo [OK] %%i

:: 检查 Node.js
where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] 需要 Node.js ^>= 18，未找到。
  echo   请安装: https://nodejs.org/
  pause
  exit /b 1
)
for /f "tokens=*" %%i in ('node --version') do echo [OK] Node.js: %%i

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] 需要 npm。
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

:: ── 2. 镜像配置 ─────────────────────────────────────────────────────────
echo [2/8] 配置镜像源...
set USE_MIRROR=%YS_USE_MIRROR%
if "%USE_MIRROR%"=="" set USE_MIRROR=true

set NPM_MIRROR=%YS_NPM_MIRROR%
if "%NPM_MIRROR%"=="" set NPM_MIRROR=https://mirrors.npmmirror.com

if "%USE_MIRROR%"=="true" (
  if defined YS_PIP_MIRROR (
    set PIP_MIRROR=%YS_PIP_MIRROR%
    echo   PIP: %PIP_MIRROR% ^(用户指定, 无回退^)
  ) else (
    echo   PIP 镜像回退链 ^(按优先级^):
    echo     - https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
    echo     - https://mirrors.aliyun.com/pypi/simple
    echo     - https://mirrors.cloud.tencent.com/pypi/simple
    echo     - https://pypi.org/simple
  )
  echo   NPM: %NPM_MIRROR%
) else (
  echo   不使用镜像源 ^(走 PyPI 官方^)
)
echo.

:: ── 3. Python 虚拟环境 ────────────────────────────────────────────────
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
:: 验证 venv 里的 pip 可用
".venv\Scripts\python.exe" -m pip --version >nul 2>nul
if errorlevel 1 (
  echo [ERROR] 虚拟环境创建成功但 pip 不可用
  echo   重装 Python 时勾选 pip, 或: python -m ensurepip --upgrade
  pause
  exit /b 1
)
echo [OK] venv pip 就绪
echo.

:: ── 4. 安装 Python 依赖 ──────────────────────────────────────────────
echo [4/8] 安装 Python 依赖...
call .venv\Scripts\activate.bat

:: 升级 pip (失败可容忍)
echo   升级 pip...
call :pip_install_robust --upgrade pip || echo   [WARN] pip 升级失败, 继续

:: 装 requirements.txt (核心依赖, 失败终止)
echo   安装 requirements.txt...
call :pip_install_robust -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Python 依赖安装失败
  echo   请检查上方 pip 错误信息, 修复后重新运行本脚本
  pause
  exit /b 1
)

:: 装 pyproject extras (开发用, 失败仅警告)
if exist "pyproject.toml" (
  echo   安装 pyproject extras ^(. [all]^)...
  call :pip_install_robust -e ".[all]" --no-deps || echo   [WARN] pyproject extras 安装失败 ^(非阻塞^)
)

:: 验证依赖图
echo   验证依赖图 ^(pip check^)...
pip check >nul 2>nul
if errorlevel 1 (
  echo   [WARN] 依赖图存在冲突, 但通常不影响运行
) else (
  echo   [OK] 依赖图一致
)

echo [OK] Python 依赖安装完成
echo.

:: ── pip 安装辅助子例程 (镜像回退) ────────────────────────────────
:: 用法: call :pip_install_robust -r requirements.txt
::      call :pip_install_robust -e ".[all]"
:: 返回: errorlevel 0=成功, 1=全部失败
:pip_install_robust
if "%USE_MIRROR%"=="true" (
  if defined PIP_MIRROR (
    :: 用户指定了单一镜像
    echo     尝试镜像: %PIP_MIRROR%
    pip install --retries 1 --timeout 15 -i "%PIP_MIRROR%" %* >nul 2>nul
    if not errorlevel 1 exit /b 0
    echo     [WARN] 镜像 %PIP_MIRROR% 失败
    exit /b 1
  ) else (
    :: 镜像回退链
    for %%m in (
      "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple"
      "https://mirrors.aliyun.com/pypi/simple"
      "https://mirrors.cloud.tencent.com/pypi/simple"
      "https://pypi.org/simple"
    ) do (
      echo     尝试镜像: %%m
      pip install --retries 1 --timeout 15 -i %%m %* >nul 2>nul
      if not errorlevel 1 (
        echo     [OK] 镜像 %%m 安装成功
        exit /b 0
      )
      echo     [WARN] 镜像 %%m 失败, 尝试下一个...
    )
    echo   [ERROR] 所有 PyPI 镜像均不可用，请检查网络
    echo   提示: YS_USE_MIRROR=false 走官方, 或 YS_PIP_MIRROR=^<URL^> 指定单一镜像
    exit /b 1
  )
) else (
  :: 不用镜像, 走 PyPI 官方
  echo     尝试 PyPI 官方源
  pip install --retries 1 --timeout 15 %* >nul 2>nul
  if not errorlevel 1 exit /b 0
  echo     [WARN] PyPI 官方源失败
  exit /b 1
)

:: ── 5. 配置文件 ──────────────────────────────────────────────────────
echo [5/8] 配置文件...
if not exist ".env" (
  if exist ".env.example" (
    copy ".env.example" ".env" >nul
    echo [OK] .env 已从 .env.example 创建
  ) else (
    echo [WARN] .env.example 不存在，跳过
  )
) else (
  echo [INFO] .env 已存在，跳过
)
echo.

:: ── 6. 数据目录 ──────────────────────────────────────────────────────
echo [6/8] 创建数据目录...
if not exist "data" mkdir data
if not exist "data\logs" mkdir data\logs
if not exist "data\sessions" mkdir data\sessions
if not exist "data\memory" mkdir data\memory
if not exist "data\backups" mkdir data\backups
echo [OK] 数据目录就绪
echo.

:: ── 7. 前端构建 ──────────────────────────────────────────────────────
echo [7/8] 安装前端依赖并构建...
cd web

if "%USE_MIRROR%"=="true" (
  call npm config set registry "%NPM_MIRROR%" 2>nul
)

call npm install --silent
if errorlevel 1 (
  echo [ERROR] 前端依赖安装失败
  cd "%PROJECT_DIR%"
  pause
  exit /b 1
)
echo [OK] 前端依赖安装完成

call npm run build
if errorlevel 1 (
  echo [ERROR] 前端构建失败
  cd "%PROJECT_DIR%"
  pause
  exit /b 1
)
echo [OK] 前端构建完成

cd "%PROJECT_DIR%"
echo.

:: ── 8. 快捷命令 + 初始化 ─────────────────────────────────────────────
echo [8/8] 安装快捷命令并执行初始化...

:: 检查 PATH 中是否有 %USERPROFILE%\.local\bin
set INSTALL_DIR=%USERPROFILE%\.local\bin
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

copy "scripts\zlink.sh" "%INSTALL_DIR%\zlink" >nul 2>&1
echo [OK] 快捷命令位置: %INSTALL_DIR%

:: 检查 PATH
echo %PATH% | findstr /i "%INSTALL_DIR%" >nul
if errorlevel 1 (
  echo [WARN] %%USERPROFILE%%\.local\bin 不在 PATH 中
  echo   请手动添加到系统环境变量 PATH 中：
  echo     %INSTALL_DIR%
)

:: 数据迁移
call .venv\Scripts\activate.bat
set PYTHONPATH=%PROJECT_DIR%
python -m scripts.migrate
if errorlevel 1 (
  echo [WARN] 数据迁移执行异常（可后续手动执行）
) else (
  echo [OK] 数据迁移检查完成
)

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
  echo   数据目录: %PROJECT_DIR%\data\
)
echo.
echo   启动方式：
echo     start.bat             生产模式启动
echo     start.bat --dev       开发模式（Vite 热更新）
echo     start.bat stop        停止服务
echo.
echo ========================================
pause