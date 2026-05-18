#!/usr/bin/env python3
"""
Lucide 图标 SVG 查询工具
用法:
    python3 lucide_icon_lookup.py search cloud        # 搜索含 cloud 的图标
    python3 lucide_icon_lookup.py get arrow-right     # 获取指定图标的 SVG
    python3 lucide_icon_lookup.py list Action        # 列出某分类所有图标
    python3 lucide_icon_lookup.py random              # 随机返回一个适合PPT的图标
"""

import sys
import random
import urllib.request
import re
LUCIDE_CDN = "https://unpkg.com/lucide@latest"

# Lucide 图标 SVG path 数据（常见图标，直接内置避免重复请求）
# 格式: name -> (category, svg_path)
LUCIDE_PATHS = {
    # Navigation
    "arrow-right": ("Navigation", "M5 12h14m-7-7 7 7-7 7"),
    "arrow-left": ("Navigation", "M19 12H5m7-7-7 7 7 7"),
    "chevron-down": ("Navigation", "M6 9l6 6 6-6"),
    "chevron-up": ("Navigation", "M18 15l-6-6-6 6"),
    "chevron-right": ("Navigation", "M9 18l6-6-6 6"),
    "menu": ("Navigation", "M4 6h16M4 12h16M4 18h16"),
    "x": ("Navigation", "M18 6L6 18M6 6l12 12"),
    "home": ("Navigation", "M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"),
    "external-link": ("Navigation", "M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6m4-3h6v6m-11-5 5-5 5-5"),
    # Action
    "plus": ("Action", "M12 5v14m-7-7h14"),
    "minus": ("Action", "M5 12h14"),
    "edit": ("Action", "M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7m-1.5-9.5a2.121 2.121 0 113 3L12 17l-4 1 1-4 9.5-9.5z"),
    "save": ("Action", "M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2zM17 21v-8H7v8M7 3v5h8"),
    "download": ("Action", "M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4m4-5 5 5-5-5-5m5 5H7"),
    "upload": ("Action", "M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4m14-7-5-5-5m-5 5L7 3"),
    "search": ("Action", "M11 19a8 8 0 100-16 8 8 0 000 16zm5-3v-2m0 0l3 3m-3-3L8 17"),
    "filter": ("Action", "M22 3H2l8 9.46V19l4 2v-8.54L22 3z"),
    "copy": ("Action", "M20 9h-9a2 2 0 00-2 2v9a2 2 0 002 2h9a2 2 0 002-2v-9a2 2 0 00-2-2zM5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"),
    "trash-2": ("Action", "M3 6h18m-2 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2m-6 5v6m4-6v6"),
    "share": ("Action", "M18 8a3 3 0 100-6 3 3 0 000 6zM6 15a3 3 0 100-6 3 3 0 000 6zM18 22a3 3 0 100-6 3 3 0 000 6zM8.59 13.51l6.83 3.98M15.41 6.51l-6.82 3.98"),
    # Status
    "check": ("Status", "M20 6L9 17l-5-5"),
    "check-circle": ("Status", "M22 11.08V12a10 10 0 11-5.93-9.14M22 4L12 14.01l-3-3"),
    "x-circle": ("Status", "M12 22a10 10 0 100-20 10 10 0 000 20zM15 9l-6 6m0-6l6 6"),
    "alert-triangle": ("Status", "M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0zM12 9v4m0 4h.01"),
    "alert-circle": ("Status", "M12 22a10 10 0 100-20 10 10 0 000 20zM12 8v4m0 4h.01"),
    "info": ("Status", "M12 22a10 10 0 100-20 10 10 0 000 20zM12 16v-4m0-4h.01"),
    "clock": ("Status", "M12 22a10 10 0 100-20 10 10 0 000 20zM12 6v6l4 2"),
    "loader": ("Status", "M12 2v4m0 12v4m10-10h-4M6 12H2m15.07-7.07l-2.83 2.83M7.76 16.24l-2.83 2.83m12.14 0l-2.83-2.83M7.76 7.76L4.93 4.93"),
    "refresh-cw": ("Status", "M23 4v6h-6m-6 6v6h6m-9.5-9.5a9 9 0 0114.06-3.54M.5 19.5a9 9 0 0114.06 3.54"),
    # Commerce
    "shopping-cart": ("Commerce", "M9 22a1 1 0 100-2 1 1 0 000 2zM20 22a1 1 0 100-2 1 1 0 000 2zM1 1h4l2.68 13.39a2 2 0 002 1.61h9.72a2 2 0 002-1.61L23 6H6m2-4h13m-13 0L3.5 18m10 0h5"),
    "credit-card": ("Commerce", "M21 4H3a2 2 0 00-2 2v12a2 2 0 002 2h18a2 2 0 002-2V6a2 2 0 00-2-2zM1 10h22"),
    "gift": ("Commerce", "M20 12v10H4V12M2 7h20v5H2zM12 22V7m-4 0h8"),
    "tag": ("Commerce", "M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82zM7 7h.01"),
    "percent": ("Commerce", "M19 5L5 19m1.5-11a3.5 3.5 0 11-7 0 3.5 3.5 0 017 0z"),
    "dollar-sign": ("Commerce", "M12 1v22m5-18H9.5a3.5 3.5 0 100 7h5a3.5 3.5 0 010 7H6"),
    # Data
    "database": ("Data", "M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zM2 12c0-3.5 2.5-6 6-6m8 6c0-3.5-2.5-6-6-6m-8 6c0-3.5 2.5-6 6-6"),
    "bar-chart": ("Data", "M12 20V10m6 10V4M6 20v-4m6 4V4"),
    "pie-chart": ("Data", "M21.21 15.89A10 10 0 118 2.83M22 12A10 10 0 0012 2v10z"),
    "trending-down": ("Data", "M23 18l-9.5-9.5-5 5L1 6m22-4h-9m-6 0v12"),
    "trending-up": ("Data", "M23 6l-9.5 9.5-5-5L1 18m22-12H11m6 12v12"),
    "activity": ("Data", "M22 12h-4l-3 9L9 3l-3 9H2"),
    "cloud": ("Cloud", "M18 10h-1.26A8 8 0 109 20h9a5 5 0 000-10z"),
    "cloud-off": ("Cloud", "M22.61 16.95A5 5 0 0018 10h-1.26a8 8 0 00-7.05-5.87M1 1l4 4m0 0l.01.01M5 9a5 5 0 004.73 4.99H9m0 0v.01M1 11.59l4 4m0 0l.01.01"),
    # Social
    "heart": ("Social", "M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"),
    "users": ("Social", "M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2m22-2v14a2 2 0 01-2 2H7a2 2 0 01-2-2v-14m8 0a4 4 0 01-4 4H9m12 0a4 4 0 01-4-4"),
    "message-circle": ("Social", "M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z"),
    "thumbs-up": ("Social", "M14 9V5a3 3 0 00-3-3l-4 9v11h11.28a2 2 0 002-1.7l1.38-9a2 2 0 00-2-2.3H14zM7 22H4a2 2 0 01-2-2v-7a2 2 0 012-2h3"),
    "share-2": ("Social", "M18 8a3 3 0 100-6 3 3 0 000 6zM6 15a3 3 0 100-6 3 3 0 000 6zM18 22a3 3 0 100-6 3 3 0 000 6zM8.59 13.51l6.83 3.98M15.41 6.51l-6.82 3.98"),
    "smile": ("Social", "M12 22a10 10 0 100-20 10 10 0 000 20zM8 14s1.5 2 4 2 4-2 4-2m-9-4h.01M17 17h.01"),
    # Security
    "shield": ("Security", "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"),
    "lock": ("Security", "M19 11H5a2 2 0 00-2 2v7a2 2 0 002 2h14a2 2 0 002-2v-7a2 2 0 00-2-2zM7 11V7a5 5 0 0110 0v4"),
    "unlock": ("Security", "M19 11H5a2 2 0 00-2 2v7a2 2 0 002 2h14a2 2 0 002-2v-7a2 2 0 00-2-2zM7 11V7a5 5 0 019.9-1"),
    "eye": ("Security", "M1 12s4-8 11-8 11 8 11 8-8 11-8 11 8 11 8zm11 3a3 3 0 100-6 3 3 0 000 6z"),
    "key": ("Security", "M21 2l-2 2m-7.61 7.61a5.5 5.5 0 11-7.778 7.778 5.5 5.5 0 017.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"),
    # Layout
    "grid": ("Layout", "M3 3h7v7H3zm11 0h7v7h-7zM3 14h7v7H3zm11 0h7v7h-7z"),
    "list": ("Layout", "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"),
    "layers": ("Layout", "M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"),
    "box": ("Layout", "M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16zM3.27 6.96L12 12.01l8.73-5.05M12 22.08V12"),
    # Media
    "play": ("Media", "M5 3l14 9-14 9V3z"),
    "pause": ("Media", "M6 4h4v16H6zm8 0h4v16h-4z"),
    "volume-2": ("Media", "M11 5L6 9H2v6h4l5 4V5zM19.07 4.93a10 10 0 010 14.14M15.54 8.46a5 5 0 010 7.07"),
    "image": ("Media", "M19 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V5a2 2 0 00-2-2zM8.5 10a1.5 1.5 0 100-3 1.5 1.5 0 000 3zM21 15l-5-5L5 21"),
    "camera": ("Media", "M23 19a2 2 0 01-2 2H3a2 2 0 01-2-2V8a2 2 0 012-2h4l2-3h6l2 3h4a2 2 0 012 2zM12 17a4 4 0 100-8 4 4 0 000 8z"),
    # Files
    "file": ("Files", "M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9zM13 2v7h7"),
    "file-text": ("Files", "M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8zM14 2v7h7M16 13H8m8 4H8m2-8H8"),
    "folder": ("Files", "M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"),
    "paperclip": ("Files", "M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"),
    # Communication
    "mail": ("Communication", "M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2zm16 2l-8 4-8-4"),
    "phone": ("Communication", "M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z"),
    "bell": ("Communication", "M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 01-3.46 0"),
    # User
    "user": ("User", "M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2m8-10a4 4 0 100-8 4 4 0 000 8z"),
    "user-plus": ("User", "M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2m12-8h.01M12 11a4 4 0 100-8 4 4 0 000 8zM18 8h.01M22 8h.01"),
    "log-in": ("User", "M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4m-5-11l5 5-5 5m5-5H9"),
    "log-out": ("User", "M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4m5 11l5-5-5-5m5 5H9"),
    # Device
    "monitor": ("Device", "M20 3H4a2 2 0 00-2 2v12a2 2 0 002 2h16a2 2 0 002-2V5a2 2 0 00-2-2zM8 21h8m-4-4v4"),
    "smartphone": ("Device", "M17 2H7a2 2 0 00-2 2v16a2 2 0 002 2h10a2 2 0 002-2V4a2 2 0 00-2-2zM12 18h.01"),
    "tablet": ("Device", "M18 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V4a2 2 0 00-2-2zM12 18h.01"),
    # Location
    "map-pin": ("Location", "M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0zM12 13a3 3 0 100-6 3 3 0 000 6z"),
    "globe": ("Location", "M12 22a10 10 0 100-20 10 10 0 000 20zM2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"),
    "navigation": ("Location", "M3 11l19-9-9 9-19-9 9z"),
    "compass": ("Location", "M12 22a10 10 0 100-20 10 10 0 000 20zM16.24 7.76l-2.12 6.36-6.36 2.12 2.12-6.36 6.36-2.12z"),
    # Time
    "calendar": ("Time", "M19 4H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V6a2 2 0 00-2-2zM16 2v4M8 2v4M3 10h18"),
    # Development
    "code": ("Development", "M16 18l6-6-6-6M8 6l-6 6 6 6"),
    "terminal": ("Development", "M4 17l6-6-6-6m8 14h8"),
    "git-branch": ("Development", "M6 3v12m0 0a3 3 0 106 0m-6 0a3 3 0 102 0m6-6v3m6-6a3 3 0 11-6 0"),
    # AI / Smart
    "cpu": ("Data", "M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18M3 9a2 2 0 012-2h4m10 0h4a2 2 0 012 2v4a2 2 0 01-2 2M3 15a2 2 0 002 2h4m10 0h4a2 2 0 002-2v-4a2 2 0 00-2-2H5"),
    "zap": ("Action", "M13 2L3 14h9l-1 8 10-12h-9l1-8z"),
    "target": ("Data", "M12 22a10 10 0 100-20 10 10 0 000 20zM12 18a6 6 0 100-12 6 6 0 000 12zM12 14a2 2 0 100-4 2 2 0 000 4z"),
    "layers": ("Layout", "M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"),
    # Scenarios 场景相关
    "briefcase": ("Commerce", "M20 7H4a2 2 0 00-2 2v10a2 2 0 002 2h16a2 2 0 002-2V9a2 2 0 00-2-2zM16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"),
    "building": ("Layout", "M6 22V4a2 2 0 012-2h8a2 2 0 012 2v18zm0 0H4a2 2 0 01-2-2V9a2 2 0 012-2h1m10 0h6m0 0v5m0-5h-6v5"),
    "settings": ("Action", "M12 15a3 3 0 100-6 3 3 0 000 6zM19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"),
    "package": ("Files", "M16.5 9.4l-9-5.19M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16zM3.27 6.96L12 12.01l8.73-5.05M12 22.08V12"),
    "truck": ("Commerce", "M5 17H3a2 2 0 01-2-2V5a2 2 0 012-2h11v12H5zm14 0h2a2 2 0 012 2v4a2 2 0 01-2 2h-2m-4 0H9v-6h6v6zM5 17a2 2 0 104 0m14 0a2 2 0 11-4 0"),
    "shield-check": ("Security", "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"),
    "award": ("Social", "M12 15l-3 6 1.5-4.5L7.5 18h9L13.5 16.5 15 18l-3-6zM8.21 3.79l-.56-.53L4 7.39l1.22 2.73 3.5 1 2.12-3.56L8.79 3.21 12 2l3.21 1.21 2.47 3.95 2.12 3.56 3.5-1 1.22-2.73-3.65-4.26-.56.53L12 2 8.21 3.79z"),
    "trending-up": ("Data", "M23 6l-9.5 9.5-5-5L1 18m22-12H11m6 12v12"),
    "zap": ("Action", "M13 2L3 14h9l-1 8 10-12h-9l1-8z"),
    "star": ("Social", "M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"),
    "book-open": ("Files", "M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2zM22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z"),
    "clipboard": ("Action", "M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2m8 0h.01M9 10h.01M15 10h.01"),
    "inbox": ("Communication", "M5 7h14l-1.5 9H6.5L5 7zm0 0V5a2 2 0 012-2h10a2 2 0 012 2v2m-14 0h14"),
    "send": ("Communication", "M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"),
}


def get_svg(name: str, size: int = 24, stroke: str = "currentColor",
             stroke_width: float = 2) -> str:
    """返回图标的 inline SVG 代码"""
    if name not in LUCIDE_PATHS:
        # 尝试从 CDN 获取
        return f"<!-- 图标 '{name}' 未收录，请补充 -->"
    _, path_data = LUCIDE_PATHS[name]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{stroke}" '
        f'stroke-width="{stroke_width}" stroke-linecap="round" '
        f'stroke-linejoin="round" class="icon icon-{name}">'
        f'<path d="{path_data}"/></svg>'
    )


def list_icons():
    """从内置图标库读取所有图标"""
    return [
        {'Icon Name': name, 'Category': cat, 'Keywords': '', 'Usage': ''}
        for name, (cat, _) in LUCIDE_PATHS.items()
    ]


def search(query: str):
    icons = list_icons()
    query = query.lower()
    results = [i for i in icons
               if query in i['Icon Name'].lower()
               or query in i['Keywords'].lower()
               or query in i['Category'].lower()]
    if not results:
        print(f"未找到含 '{query}' 的图标")
        return
    print(f"找到 {len(results)} 个结果:\n")
    for i in results:
        print(f"  [{i['Category']}] {i['Icon Name']} — {i['Usage']}")


def get_icon(name: str, size: int = 24, stroke: str = "#E60012"):
    """获取指定图标的完整 SVG HTML"""
    svg = get_svg(name, size, color)
    print(f"\n图标: {name}")
    print(f"颜色: {stroke}")
    print(f"\nSVG 代码:\n{svg}\n")
    # 同时输出 HTML 使用示例
    print("HTML 使用示例:")
    print(f'  <span class="icon-wrap">{svg}</span>')
    return svg


def list_by_category(category: str):
    icons = list_icons()
    results = [i for i in icons if i['Category'].lower() == category.lower()]
    if not results:
        print(f"未找到分类 '{category}'，可用分类:")
        cats = sorted(set(i['Category'] for i in icons))
        for c in cats:
            print(f"  - {c}")
        return
    print(f"分类 '{category}' 共 {len(results)} 个图标:\n")
    for i in results:
        svg = get_svg(i['Icon Name'], size=20, stroke="#E60012")
        print(f"  {i['Icon Name']:20s} — {i['Usage']}")


def random_icon():
    """返回一个适合 PPT 的图标（主要是 Action/Status/Navigation 类）"""
    icons = list_icons()
    # 优先 Action/Status/Navigation
    priority = [i for i in icons if i['Category'] in
                ('Action', 'Status', 'Navigation', 'Commerce', 'Social')]
    if not priority:
        priority = icons
    chosen = random.choice(priority)
    print(f"\n随机推荐: {chosen['Icon Name']} [{chosen['Category']}]")
    print(f"用法: {chosen['Usage']}")
    get_svg(chosen['Icon Name'])


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == 'search' and len(sys.argv) >= 3:
        search(sys.argv[2])
    elif cmd == 'get' and len(sys.argv) >= 3:
        get_icon(sys.argv[2])
    elif cmd == 'list' and len(sys.argv) >= 3:
        list_by_category(sys.argv[2])
    elif cmd == 'random':
        random_icon()
    else:
        print(__doc__)
