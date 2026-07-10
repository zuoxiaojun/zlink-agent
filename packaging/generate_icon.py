#!/usr/bin/env python3
"""Generate app-icon.ico from app-icon.png for Windows packaging."""

from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("[WARN] Pillow 未安装，跳过图标生成。")
    print("       运行: pip install Pillow")
    exit(0)

src = Path(__file__).resolve().parent / "app-icon.png"
dst = src.with_suffix(".ico")

if not src.exists():
    print(f"[WARN] {src} 不存在，跳过图标生成。")
    exit(0)

img = Image.open(src)
# ICO requires at least one of these sizes: 16, 32, 48, 64, 128, 256
sizes = [16, 32, 48, 64, 128, 256]
img.save(dst, format="ICO", sizes=[(s, s) for s in sizes if s <= max(img.size)])
print(f"[OK] 已生成图标: {dst}")
