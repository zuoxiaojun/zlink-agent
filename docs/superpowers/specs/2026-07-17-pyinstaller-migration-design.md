# PyInstaller 迁移设计

## 1. 问题背景

ZLink Agent Electron 客户端当前使用 `scripts/bundle-python.sh`（Homebrew Framework venv）打包 Python 运行环境，但 macOS Framework Python 的 interpreter binary **硬编码**了 Homebrew stdlib 路径（`/opt/homebrew/.../lib/python3.14`），用户机器上没有这些路径，导致 `import os` 都炸。

之前的修复尝试（`PYTHONHOME` 环境变量 + `relocate_python_bundle()` dylib 修复）属于"从破损的打包方案向外修补"，每个 Python 小版本升级布局都变，dylib 路径断裂问题层出不穷。

## 2. 方案

选用 PyInstaller `--onefile` 模式，将 FastAPI 后端（`backend/main.py` + uvicorn + 所有依赖）打包成**单文件二进制** `zlink-backend`。

### 为什么是 PyInstaller

- Python 生态标准打包工具，macOS/Windows/Linux 三平台支持
- 正确处理 stdlib 路径、动态库收集和重定位
- 单文件部署，没有 `sys.path`/dylib 路径断裂风险
- 构建速度快（秒级 vs bundle-python.sh 几分钟）

### 不采用的方案

**纯 Electron + 后端独立部署**：让用户自行 `pip install` 运行后端——失去"自包含桌面客户端"的核心体验。

## 3. 改动文件清单

| 文件 | 当前状态 | 目标状态 |
|------|---------|---------|
| `scripts/build-electron.sh` | [2/4] 调用 `bash scripts/bundle-python.sh` | [2/4] 改为 `pyinstaller backend/main.py --onefile --name zlink-backend`，并添加 PyInstaller 构建参数 |
| `scripts/bundle-python.sh` | Homebrew venv 打包脚本 | 保留作为参考，不再调用 |
| `scripts/build_utils.py` | `relocate_python_bundle` + dylib 修复 | 从构建流程中移除（保留文件） |
| `electron/main.js` | `findBundledPython()` 找 `python-bundle/bin/python3` + `backend_launcher.py` | 改为找 `zlink-backend` 单文件二进制，直接 spawn |
| `electron/backend_launcher.py` | Python 后端启动入口（加 sys.path hack） | 弃用（PyInstaller 单文件不需要此脚本） |
| `electron-builder.yml` | `extraResources` 拉入 `python-bundle/`（~80MB venv）+ `app/`（源码） | 改为拉入 PyInstaller 产物 `dist/zlink-backend`（~40-60MB），移除 `app/` 源码包（已编译进二进制） |

## 4. PyInstaller 打包参数

```
入口点: backend/main.py
输出名: zlink-backend
模式: --onefile (单文件)

必要参数:
  --hidden-import uvicorn          # uvicorn 是字符串 import
  --hidden-import uvicorn.logging
  --hidden-import uvicorn.loops
  --hidden-import uvicorn.loops.auto
  --hidden-import uvicorn.protocols
  --hidden-import uvicorn.protocols.http
  --hidden-import uvicorn.protocols.http.auto
  --hidden-import uvicorn.middleware
  --hidden-import uvicorn.middleware.asgi2
  --hidden-import uvicorn.middleware.debug
  --hidden-import uvicorn.middleware.proxy_headers
  --hidden-import uvicorn.middleware.wsgi
  --hidden-import oracledb          # ERP NC 动态连接
  --add-data "agent/skills:skills" # 20 个内置技能的 SKILL.md 数据文件

隐藏导入原因：uvicorn 使用字符串引用加载组件（如 "uvicorn.protocols.http.auto"），
PyInstaller 的静态分析无法发现这些隐式依赖。
```

### 运行时目录结构变化（PyInstaller 解包后）

PyInstaller `--onefile` 在启动时自解压到 `_MEIPASS` 临时目录：

```
_MEIPASS/
├── backend/
│   └── main.py
├── agent/
│   ├── ... (所有 Python 模块)
│   └── skills/          ← --add-data 复制过来
│       ├── yonsuite/SKILL.md
│       └── ... (20 个技能目录)
└── ... (所有 site-packages 依赖)
```

项目的 `DATA_DIR`（`~/.zlink-agent/data/`）不受影响——它由环境变量或 `Path.home()` 解析，与 `_MEIPASS` 独立。

### 对 `backend/main.py` 的影响

`backend/main.py:10-12` 的 `sys.path` 插入在 PyInstaller 中不再必要（所有模块已在 `_MEIPASS` 中），但无害，PyInstaller 不会因为这个报错。

Chart MCP server 路径解析（`main.py:93`）的 `Resources/mcp-chart/` 是 electron-builder 的 extraResources 挂载路径，`_MEIPASS` 外，不受 PyInstaller 影响。

## 5. Electron 启动流程变化

```
旧流程:
  Electron → spawn(python3, [backend_launcher.py])
    ├─ backend_launcher.py: sys.path 插入 app/ 目录
    ├─ backend_launcher.py: import uvicorn; uvicorn.run("backend.main:app")
    └─ 需要 PYTHONPATH 环境变量给 MCP 子进程

新流程:
  Electron → spawn(zlink-backend, [])
    ├─ 二进制自解压到 _MEIPASS
    ├─ 自动运行 backend.main:app（PyInstaller 入口）
    ├─ sys.path 已经包含所有模块
    └─ MCP 子进程如果需要 agent/ 模块，通过 _MEIPASS 路径或环境变量
```

`electron/main.js` 的改动：
- `findBundledPython()` → `findBackendBinary()`，在 `Resources/zlink-backend` 找单文件
- 不再需要 `findBackendLauncher()` 和 `PYTHONPATH` 环境变量
- `stopBackend()` 逻辑不变（kill 子进程）

## 6. electron-builder.yml 变化

```yaml
# 旧:
extraResources:
  - from: build/python-bundle/
    to: python-bundle          # ~80MB Homebrew venv
  - from: .
    to: app                    # ~1000+ 文件的项目源码（PYTHONPATH 使用）
  - from: electron/
    to: .
    filter: ["backend_launcher.py"]  # 启动脚本
  - from: node_modules/@antv/mcp-server-chart/
    to: mcp-chart              # Chart MCP server（不变）

# 新:
extraResources:
  - from: dist/zlink-backend
    to: .
  - from: node_modules/@antv/mcp-server-chart/
    to: mcp-chart              # 保留 Chart MCP
```

`app/` 源码包和 `backend_launcher.py` 都移除：所有 Python 代码已编译进 PyInstaller 二进制，不再需要 `PYTHONPATH` 给 MCP 子进程（当前 MCP 子进程只有 Node.js 的 Chart，不需要 Python 路径）。

## 7. 构建流程变化

```
[1/4] 构建前端          npm run build          (不变)
[2/4] 打包 Python后端   pyinstaller ...         (原 bundle-python.sh)
[3/4] 打包 Electron     npx electron-builder    (不变)
[4/4] 清理              python3 build_utils.py  (保留)
```

## 8. 边界情况与风险

| 风险 | 缓解措施 |
|------|---------|
| PyInstaller 漏收集某个隐式 import | `--hidden-import` 列表覆盖 uvicorn 组件；构建后运行 `zlink-backend` 验证 |
| agent/skills/ 目录不在 _MEIPASS | `--add-data` 确保复制所有 SKILL.md；`skills_tool.py:SKILLS_DIR` 使用 `Path(__file__).resolve()`，在 PyInstaller 中会自动解析到 _MEIPASS |
| macOS 代码签名问题 | 和旧方案一样需要 hardenedRuntime + 签名流程；这不是新引入的问题 |
| 二进制体积变大 | PyInstaller 单文件约 40-60MB（含 Python 解释器 + stdlib + 所有依赖），比旧的 venv ~80MB 反而小 |
| MCP 子进程找不到 agent/ 模块 | MCP 子进程是 Node.js（chart）或独立 Python，不依赖后端 Python 路径；如果后续有 Python MCP，通过环境变量 `PYTHONPATH` 传入 _MEIPASS 路径 |
| 进程退出时的临时目录清理 | PyInstaller 自动清理 `_MEIPASS`，无需额外处理 |

## 9. 验证标准

1. `pyinstaller backend/main.py --onefile --name zlink-backend` 构建成功，退出码 0
2. `./dist/zlink-backend` 能独立启动，FastAPI 在 8089 端口响应
3. `GET /api/health` 返回 200
4. 内置技能列表 `GET /api/skills` 返回 20 个技能
5. `bash scripts/build-electron.sh` 构建出 `.dmg`
6. 安装后的 `.dmg` 启动后端不崩溃，`~/.zlink-agent/data/` 正常生成