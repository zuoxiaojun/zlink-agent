"""Build utilities — cross-platform helpers for build scripts."""

import os
import shutil
import sys
from pathlib import Path


def is_windows() -> bool:
    """Detect if running under Windows (MSYS2/Git Bash/Cygwin or native Windows)."""
    return sys.platform.startswith("win") or os.name == "nt"


def python_bin_path(bundle_dir: str) -> str:
    """Return the Python executable path inside a venv bundle dir.

    Unix:    <bundle_dir>/bin/python
    Windows: <bundle_dir>/Scripts/python.exe
    """
    if is_windows():
        return os.path.join(bundle_dir, "Scripts", "python.exe")
    return os.path.join(bundle_dir, "bin", "python")


def clean_pycache(root_dir: str) -> None:
    """Remove __pycache__ dirs and .pyc files recursively (cross-platform)."""
    root = Path(root_dir)
    for item in root.rglob("__pycache__"):
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
    for item in root.rglob("*.pyc"):
        if item.is_file():
            item.unlink(missing_ok=True)


def remove_test_dirs(root_dir: str) -> None:
    """Remove Python 'test' directories under lib/ (cross-platform)."""
    root = Path(root_dir)
    lib_python = root / "lib"
    if lib_python.is_dir():
        for py_ver_dir in lib_python.iterdir():
            test_dir = py_ver_dir / "test"
            if test_dir.is_dir():
                shutil.rmtree(test_dir, ignore_errors=True)


def dir_size_mb(root_dir: str) -> str:
    """Return human-readable directory size in MB (cross-platform)."""
    total = 0
    root = Path(root_dir)
    for item in root.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                pass
    return f"{total / (1024 * 1024):.1f} MB"


def remove_paths(*paths: str) -> None:
    """Remove files or directories (cross-platform)."""
    for p in paths:
        path = Path(p)
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)