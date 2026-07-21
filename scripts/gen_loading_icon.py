#!/usr/bin/env python3
"""同步应用图标：packaging/app-icon.png → electron/loading.html 内嵌图标 + web/public/favicon.png。

依赖 macOS 自带 sips（零第三方依赖）。在仓库根目录运行：

    python3 scripts/gen_loading_icon.py

loading.html 中的图标位于 <!-- ICON:START --> / <!-- ICON:END --> 标记之间，脚本幂等替换。
"""
from __future__ import annotations

import base64
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_ICON = ROOT / "packaging" / "app-icon.png"
LOADING_HTML = ROOT / "electron" / "loading.html"
FAVICON = ROOT / "web" / "public" / "favicon.png"

ICON_START = "<!-- ICON:START -->"
ICON_END = "<!-- ICON:END -->"


def sips(*args: str) -> None:
    subprocess.run(["sips", *args], check=True, capture_output=True)


def main() -> None:
    if not APP_ICON.exists():
        sys.exit(f"图标不存在: {APP_ICON}")

    # 1) favicon：256px 真 PNG（修复旧文件实为 JPEG 冒充 PNG 的问题）
    sips("-z", "256", "256", "-s", "format", "png", str(APP_ICON), "--out", str(FAVICON))
    print(f"favicon 已更新: {FAVICON}")

    # 2) loading.html 内嵌 144px base64 图标
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        sips("-z", "144", "144", "-s", "format", "png", str(APP_ICON), "--out", str(tmp_path))
        b64 = base64.b64encode(tmp_path.read_bytes()).decode("ascii")
    finally:
        tmp_path.unlink(missing_ok=True)
    img_tag = f'{ICON_START}<img class="logo-tile" src="data:image/png;base64,{b64}" alt="ZLink Agent" />{ICON_END}'

    html = LOADING_HTML.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(ICON_START) + r".*?" + re.escape(ICON_END), re.DOTALL)
    if not pattern.search(html):
        sys.exit("loading.html 缺少 ICON 标记，请检查文件")
    html = pattern.sub(img_tag, html)
    LOADING_HTML.write_text(html, encoding="utf-8")
    print(f"loading.html 图标已更新: {LOADING_HTML}")


if __name__ == "__main__":
    main()
