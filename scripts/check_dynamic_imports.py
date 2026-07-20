"""扫描代码中的动态导入，并与 PyInstaller hidden imports 清单比对。

检测模式：
- 函数/方法内部的 import
- try/except ImportError 块中的 import
- importlib.import_module() 调用
- __import__() 调用

过滤规则：
- 跳过标准库
- 跳过项目内部模块（agent/backend/mcp_server）
- 跳过 tests/ 目录
- 跳过 agent/skills/*/scripts/ 下的技能脚本依赖（可选安装，不进核心包）
- 跳过相对导入（from . import xxx / from .. import xxx）

输出：
- 发现的动态导入模块
- 已在 hidden imports 中的（OK）
- 未在 hidden imports 中的（需要确认/补录）

用法：
    python scripts/check_dynamic_imports.py
    python scripts/check_dynamic_imports.py --verbose
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.pyinstaller_hidden_imports import get_hidden_imports  # noqa: E402

# 已知可选依赖：扫描时提示但不强制要求进 hidden imports
OPTIONAL_DEPENDENCIES: dict[str, str] = {}


def _is_stdlib(module: str) -> bool:
    """判断是否是标准库模块。"""
    stdlib = {
        "__future__", "abc", "argparse", "ast", "asyncio", "base64", "collections",
        "colorsys", "concurrent", "contextlib", "copy", "csv", "dataclasses", "datetime",
        "enum", "fcntl", "fnmatch", "functools", "glob", "hashlib", "hmac", "html", "http",
        "importlib", "inspect", "io", "itertools", "json", "logging",
        "math", "mimetypes", "multiprocessing", "os", "pathlib", "pickle", "platform",
        "queue", "random", "re", "select", "shutil", "signal", "socket", "sqlite3",
        "ssl", "stat", "statistics", "string", "subprocess", "sys", "tempfile", "textwrap",
        "threading", "time", "tomllib", "traceback", "typing", "unittest", "urllib", "uuid",
        "warnings", "weakref", "webbrowser", "xml", "zipfile",
    }
    first = module.split(".")[0]
    return first in stdlib


def _is_local(module: str) -> bool:
    """判断是否是项目内部模块。"""
    first = module.split(".")[0]
    return first in {"agent", "backend", "mcp_server", "scripts", "tests"}


def _should_skip_file(path: Path) -> bool:
    """判断是否应该跳过该文件。"""
    parts = path.parts
    # 跳过测试目录
    if "tests" in parts:
        return True
    # 跳过技能脚本（可选依赖，不进核心包）
    if "agent" in parts and "skills" in parts:
        idx = parts.index("skills")
        if len(parts) > idx + 2 and parts[idx + 2] in {"scripts", "eval-viewer"}:
            return True
    # 跳过示例和测试
    if "examples" in parts or "tests" in parts[-2:]:
        return True
    return False


def _extract_module_name(node: ast.AST) -> list[str]:
    """从 AST 节点提取模块名。"""
    names = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            names.append(alias.name)
    elif isinstance(node, ast.ImportFrom):
        # 跳过相对导入
        if node.level > 0:
            return []
        if node.module:
            names.append(node.module)
    return names


class DynamicImportVisitor(ast.NodeVisitor):
    """AST 访问器：收集动态导入的模块名。"""

    def __init__(self):
        self.imports: list[tuple[str, int, str]] = []  # (module, lineno, context)
        self._in_function = 0
        self._in_try_except = 0

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._in_function += 1
        self.generic_visit(node)
        self._in_function -= 1

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._in_function += 1
        self.generic_visit(node)
        self._in_function -= 1

    def visit_Try(self, node: ast.Try):
        # 检查 except 块是否捕获 ImportError
        has_import_error = any(
            isinstance(handler.type, ast.Name) and handler.type.id == "ImportError"
            for handler in node.handlers
        )
        if has_import_error:
            self._in_try_except += 1
        self.generic_visit(node)
        if has_import_error:
            self._in_try_except -= 1

    def visit_Import(self, node: ast.Import):
        for module in _extract_module_name(node):
            self._record(module, node.lineno)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        for module in _extract_module_name(node):
            self._record(module, node.lineno)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # importlib.import_module("xxx")
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "importlib"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            self._record(node.args[0].value, node.lineno, "importlib")

        # __import__("xxx")
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "__import__"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            self._record(node.args[0].value, node.lineno, "__import__")

        self.generic_visit(node)

    def _record(self, module: str, lineno: int, context: str = ""):
        if _is_stdlib(module) or _is_local(module):
            return
        ctx = context or ("try-except" if self._in_try_except else "function" if self._in_function else "dynamic")
        self.imports.append((module, lineno, ctx))


def _is_package_relative(module: str, importing_file: Path) -> bool:
    """判断模块是否是导入文件所在包的相对导入。"""
    # 例如: 文件 agent/erp_clients/yonsuite/ys_client.py 导入 modules.todo
    # 检查 agent/erp_clients/yonsuite/modules/todo.py 是否存在
    parts = module.split(".")
    candidate = importing_file.parent / "/".join(parts)
    if candidate.with_suffix(".py").exists():
        return True
    if (candidate / "__init__.py").exists():
        return True
    return False


def scan_file(path: Path) -> list[tuple[str, int, str]]:
    """扫描单个 Python 文件。"""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError):
        return []
    visitor = DynamicImportVisitor()
    visitor.visit(tree)
    # 过滤包内相对导入
    return [
        (m, lineno, ctx) for m, lineno, ctx in visitor.imports
        if not _is_package_relative(m, path)
    ]


def scan_project() -> dict[str, list[tuple[str, int, str]]]:
    """扫描整个项目，返回 {module: [(file, lineno, context), ...]}。"""
    results: dict[str, list[tuple[str, int, str]]] = {}
    skip_dirs = {".venv", "__pycache__", ".git", "node_modules", "dist", "build", ".codegraph"}
    for path in PROJECT_ROOT.rglob("*.py"):
        # 跳过虚拟环境、缓存、构建产物
        if any(part in skip_dirs for part in path.parts):
            continue
        if _should_skip_file(path):
            continue
        for module, lineno, context in scan_file(path):
            rel = path.relative_to(PROJECT_ROOT)
            results.setdefault(module, []).append((str(rel), lineno, context))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="扫描代码中的动态导入")
    parser.add_argument("--verbose", "-v", action="store_true", help="显示详细位置信息")
    args = parser.parse_args()

    hidden_imports = set(get_hidden_imports())
    dynamic_imports = scan_project()

    if not dynamic_imports:
        print("未发现动态导入。")
        return 0

    missing = []
    covered = []
    optional = []

    for module, locations in sorted(dynamic_imports.items()):
        # 检查模块本身或其父包是否在 hidden imports 中
        parts = module.split(".")
        found = any(".".join(parts[:i]) in hidden_imports for i in range(1, len(parts) + 1))
        entry = (module, locations)
        if found:
            covered.append(entry)
        elif module in OPTIONAL_DEPENDENCIES:
            optional.append(entry)
        else:
            missing.append(entry)

    print("=" * 60)
    print("动态导入扫描报告")
    print("=" * 60)
    print(f"\n已覆盖 ({len(covered)}):")
    for module, locations in covered:
        print(f"  [OK] {module}")
        if args.verbose:
            for file, lineno, ctx in locations:
                print(f"       {file}:{lineno} ({ctx})")

    if optional:
        print(f"\n可选依赖 ({len(optional)}):")
        for module, locations in optional:
            note = OPTIONAL_DEPENDENCIES.get(module, "")
            print(f"  [OPTIONAL] {module} — {note}")
            if args.verbose:
                for file, lineno, ctx in locations:
                    print(f"       {file}:{lineno} ({ctx})")

    if missing:
        print(f"\n未覆盖 ({len(missing)}):")
        for module, locations in missing:
            print(f"  [MISSING] {module}")
            for file, lineno, ctx in locations:
                print(f"       {file}:{lineno} ({ctx})")
        print("\n建议：")
        for module, _ in missing:
            print(f'  将 "{module}" 加入 scripts/pyinstaller_hidden_imports.py')
        return 1

    print("\n所有核心动态导入均已覆盖。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
