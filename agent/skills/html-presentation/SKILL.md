---
name: html-presentation
description: "用友/YonSuite 风格 HTML 演示文稿制作规范：红白灰配色、白底卡片式布局、七类标准页型，产出单文件 HTML slides。"
version: 1.0.0
author: ZLink Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  zlink:
    tags: [presentation, slides, html, yonsuite, 演示文稿, ppt]
    related_skills: [pptx-generator]
---

# HTML Presentation（用友风格 HTML 演示文稿）

当用户要求制作演示文稿、slides、产品介绍页、方案汇报页，且接受 HTML 形式时，使用本规范。**产出必须是单个自包含 HTML 文件**（内联 CSS/JS，无外部依赖，可直接双击打开或投影）。

内容文案素材见 `assets/yonsuite-official-content.md`（品牌定位语、十大领域模块、AI 能力点，可直接引用）。

## 设计原则

- 白底为主，企业级、现代简约、大量留白；
- 每页一个核心信息，拒绝堆砌；
- 16:9 画幅，建议每页 `1280×720`，用 `<section class="slide">` 分页，键盘 ←/→ 或点击翻页（附 30 行以内的极简翻页脚本）。

## 配色体系

| 角色 | 色值 | 用途 |
|------|------|------|
| 品牌红 | `#D43838` | 标题强调、主按钮、关键数据、装饰线段 |
| 品牌红-浅 | `#FFF0F0` | 强调色卡片底、标签底 |
| 正文 | `#1D2129` | 标题与正文 |
| 次要 | `#4E5969` / `#86909C` | 副标题、说明文字 |
| 背景 | `#FFFFFF` / `#F2F3F5` | 页面底 / 卡片间隔底 |
| 边框 | `#E5E6EB` | 卡片描边、分割线 |

- 红 : 白 : 灰 ≈ 1 : 7 : 2，红色只作点睛，不大面积铺底；
- 图表配色：主系列 `#D43838`，其后 `#E65C5C`、`#86909C`、`#4E5969`、`#FFC0C0`，避免红绿撞色；
- 箭头/装饰渐变：`#D43838 → #E88B8B`（135deg）；
- 科技风变体可用官网蓝 `#0052CC` 渐变替换品牌红（见 `assets/yonsuite-official-content.md` 视觉关键词），但一份文稿内只选一种主色。

## 字体规范

- 字体栈：`-apple-system, "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif`；
- 字号层级：页标题 36–44px / 副标题 20–24px / 正文 16–18px / 注释 12–14px；
- 行距 1.5–1.6，标题可用 `letter-spacing: -0.01em` 收紧；
- 禁止：斜体正文、全大写中文标题、一页超过 3 种字号层级以外的混排。

## 布局规范

- 页边距 ≥ 64px，内容区 12 列网格，卡片间距 24px；
- 卡片：白底、圆角 12–16px、`border: 1px solid #E5E6EB`、阴影 `0 4px 16px rgba(0,0,0,0.08)`；
- 左对齐优先，居中对齐仅用于封面/结束页；
- 图片必须服务于信息，不用纯装饰大图；配图区域保持统一圆角。

## 标准页型（按需组合）

| 页型 | 结构 |
|------|------|
| Hero 封面 | 居中大标题 + 副标题 + 品牌色装饰线段（参考 `assets/hero-cover-ref.png`） |
| Pain/Solution | 左右双栏：痛点（灰底） vs 方案（红浅底） |
| Feature Cards | 3–6 张能力卡片网格，图标 + 短标题 + 一行说明 |
| Architecture | 分层架构图，纯 CSS 盒子 + 连线，层色递减 |
| Scenarios | 场景页：左文右图或上图下文，每页一个场景 |
| 能力总览 | 白底卡片矩阵（参考十大领域模块文案） |
| End 结束页 | 致谢 + 联系方式 + logo（参考 `assets/end-slide-ref.png`） |

## 装饰元素（克制使用，每页 ≤ 2 种）

- 标题左侧三色短线段（红/橙/灰，4px 高）；
- 左上角几何切片 + 品牌 logo（logo 文件见 `assets/logo/`，参考 `assets/topleft-logo.png`）；
- 底部网格/点阵纹理（CSS radial-gradient 实现即可）；
- 右上角圆点序列作页码/步骤指示（参考 `assets/topright-dots-ref.png`）；
- 图标统一用 Lucide 风格线性 SVG：运行 `scripts/lucide_icon_lookup.py search <关键词>` 查图标、`get <名称>` 取 SVG path，内联使用，`stroke="currentColor"`。

## Logo 与图片嵌入

- 所有图片必须内嵌：`assets/logo/` 下提供现成 base64（`*.b64`），直接用 `<img src="data:image/png;base64,...">`；
- 新增图片先压到 < 200KB 再转 base64；
- 常见坑：base64 串损坏时先查 PNG 签名（`\x89PNG`）与 IDAT 完整性，不要在 HTML 里引用本地文件路径。

## 可选增强（用户要求"炫酷"时才加）

- Canvas 粒子/网格动画背景（仅封面与结束页）；
- 卡片悬浮上浮 + 发光：`transform: translateY(-4px)` + 阴影加深，过渡 0.25s。

## 交付检查清单

- [ ] 单文件、无外部请求（字体/CDN/图片全部内联）；
- [ ] 每页 1280×720，翻页可用；
- [ ] 红色面积 ≤ 10%，无红绿撞色；
- [ ] 字号层级不超过规范，文字不溢出卡片；
- [ ] Chrome/Safari 打开版式一致。
