---
name: html-presentation
description: |
  Create YonSuite/用友风格的HTML演示文稿。白底品牌风+几何点缀+底部品牌位，支持翻页式交互和全屏演示。
  触发词：做个 PPT 风格的 HTML、做个演示网页、做成交互式网页、做个翻页式演示文稿、做个幻灯片网页、HTML 演示、网页版 PPT、用友风格、YonSuite风格、YS风格。
  Also use when asked: create presentation, PPT-style HTML, slide deck, scrollable HTML, fullscreen demo format, YonSuite style, 用友风格.
---

# HTML Presentation Skill

## 两个版本

| 版本 | 触发条件 | 核心特征 |
|------|---------|---------|
| **PPT版** | 演示汇报、方案宣讲、投影场景 | 翻页式、封面+内容页+结尾页、键盘翻页 |
| **订单版** | 数据分析、数据看板、监控大屏 | 上下/左右分栏、KPI卡片+图表+明细表、无翻页 |

### 订单版典型元素
- **KPI 区域**：今日订单数、成交金额、环比增长……红色数字突出重点
- **图表区**：柱状图/折线图展示趋势，灰色系为主，红色强调拐点/异常
- **明细表格**：订单明细行，红色标出异常/逾期行
- **装饰**：左上角 Logo、右下角品牌位、三色短线装饰标题
- **布局**：上下分栏（KPI → 图表 → 表格）或左右分栏（图表 ←→ 表格）

### PPT版典型元素
- 翻页式演示，键盘← →翻页、全屏演示
- 右上角步骤圆点导航
- 封面页 + 内容页 + 结束页

---

## Design Philosophy（设计理念）

**以简约的风格、统一的规范和秩序，促进"信息传递"，强化"视觉记忆"。**

一切设计决策围绕这两个目标：
- **信息传递**：层级清晰、重点突出、阅读路径明确
- **视觉记忆**：统一配色、重复规范、关键点用红色强化

**参考用友官方演示风格**：白色背景 + 品牌三色 + 几何点缀 + 底部品牌位。

**参考用友官方演示风格**：白色背景 + 品牌三色 + 几何点缀 + 底部品牌位。

## 配色体系：

```
--bg: #FFFFFF;
--bg-alt: #F5F5F7;      /* 极浅灰背景（卡片/分割） */
--bg-grid: #FAFAFA;     /* 网格纹理底色 */
--text: #4A4A4A;         /* 深灰（正文） */
--text-secondary: #6E6E73;
--text-sub: #86868B;
--red: #E60012;          /* 用友红（强调/重点） */
--orange: #FF6B00;        /* 活力橙 */
--blue: #0071E3;          /* 科技蓝 */
--yellow: #FF9500;        /* 橙黄 */
--border: rgba(0,0,0,0.08);
```

### 红色使用约束（重要）
- 红色用于**强调重点**
- 红色在页面中占比**不超过 20%**
- **仅在箭头上使用红白渐变色**
- 灰色可以渐变

### 箭头渐变规范
```css
/* 仅在箭头上使用红白渐变 */
.arrow-gradient {
  background: linear-gradient(90deg, #E60012, #FFFFFF);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
/* 或渐变填充 */
.arrow-fill {
  fill: url(#redWhiteGradient);
}
```

## Logo 资产规范（Logo Assets）

**存储路径**：`skills/yonyou-html-presentation/assets/logo/`（技能内置素材目录）

**命名规范**：
- `current-logo.png` — 当前使用的 Logo，每次更新素材后替换此文件（HTML 引用这个文件名，保持不变）
- `yonsuite-logo.png` — YonSuite 官方标准 Logo（品牌右下角用）
- 其他素材按用途命名，如 `topleft-logo.png`、`logo-dark.png` 等

**已收录素材清单**：

| 文件名 | 内容描述 | 配色 | 用途 |
|--------|---------|------|------|
| `current-logo.png` | 用友红灰黑 Logo（红色中文+灰色yonyou，黑底） | 红/灰/黑 | 当前默认 |
| `logo-001.png` | 同上（公子提供的原图版本） | 红/灰/黑 | 备用/原始版本 |
| `topleft-logo.png` | 左上角装饰用老 Logo | — | 历史参考 |
| `yonsuite-official-content.md` | YonSuite官网文案素材（十大领域模块完整描述/AI能力/CTA/品牌语） | — | 内容参考 |
| `yonsuite-logo.png` | 右下角品牌位用标准 Logo | 红/白 | 品牌 Footer |
| `end-slide-ref.png` | 结束页视觉参考 | — | 结束页模板 |
| `hero-cover-ref.png` | Hero区封面参考 | — | 首页模板 |
| `topright-dots-ref.png` | 右上角步骤圆点参考 | — | 导航圆点 |

**使用规则**：
- 每页都必须在左上角显示 Logo（通过 body-level fixed `img.page-logo` 实现）
- 所有页使用同一张 `current-logo.png`，保持完全一致
- 公子提供新 Logo 素材 → 替换 `assets/logo/current-logo.png` → 所有页自动生效
- Logo 在 CSS 中使用 `position: fixed; top: 20px; left: 24px; z-index: 1000`，不受 slides-wrapper translateX 影响

**HTML 中的 Logo 引用**：
```html
<!-- 放在 body 内、slides-wrapper 外面 -->
<img src="assets/logo/current-logo.png" class="page-logo" alt="Logo">

<!-- CSS -->
.page-logo {
  position: fixed;
  top: 20px; left: 24px;
  width: 120px; z-index: 1000;
  pointer-events: none;
}
```

### Logo CDN 引用规范（2026-04-29 启用）

**CDN 优先，不再使用 base64 嵌入。Logo 统一托管在 Gitee。**

| 用途 | 文件 | CDN URL |
|------|------|---------|
| 左上角 Logo | `current-logo.png` | `https://gitee.com/leftxiaojun/yonyou-html-presentation/raw/main/assets/logo/current-logo.png` |
| 右下角品牌位 | `yonsuite-logo.png` | `https://gitee.com/leftxiaojun/yonyou-html-presentation/raw/main/assets/yonsuite-logo.png` |

**注意**：Gitee Raw 链接有 302 重定向，浏览器直接用在 `<img src>` 中会自动跟随跳转。

```html
<!-- 左上角 logo -->
<img src="https://gitee.com/leftxiaojun/yonyou-html-presentation/raw/main/assets/logo/current-logo.png" class="page-logo" alt="YonSuite">

<!-- 右下角品牌位 logo -->
<div class="brand-footer">
  <img src="https://gitee.com/leftxiaojun/yonyou-html-presentation/raw/main/assets/yonsuite-logo.png" class="brand-logo-img" alt="YonSuite">
  <span>成长型企业就用YonSuite</span>
</div>

<!-- 结束页 logo -->
<img src="https://gitee.com/leftxiaojun/yonyou-html-presentation/raw/main/assets/logo/current-logo.png" class="end-logo-img" alt="YonSuite">
```

**Logo 更新流程**：
1. 替换本地 `assets/logo/current-logo.png` 或 `assets/yonsuite-logo.png`
2. 同步上传到 Gitee：
   ```bash
   # 当前目录：agent/skills/html-presentation/
   TOKEN=$(grep GITEE_TOKEN .env | cut -d= -f2)
   OWNER=leftxiaojun
   REPO=yonyou-html-presentation
   BRANCH=main

   # 上传 current-logo.png
   curl -s -X POST "https://gitee.com/api/v5/repos/${OWNER}/${REPO}/contents/assets/logo/current-logo.png?access_token=${TOKEN}" \
     -H "Content-Type: application/json" \
     -d "{\"message\":\"update logo\",\"content\":\"$(base64 -i assets/logo/current-logo.png | tr -d '\n')\",\"branch\":\"${BRANCH}\"}"

   # 上传 yonsuite-logo.png
   curl -s -X POST "https://gitee.com/api/v5/repos/${OWNER}/${REPO}/contents/assets/yonsuite-logo.png?access_token=${TOKEN}" \
     -H "Content-Type: application/json" \
     -d "{\"message\":\"update logo\",\"content\":\"$(base64 -i assets/yonsuite-logo.png | tr -d '\n')\",\"branch\":\"${BRANCH}\"}"
   ```
3. CDN 缓存更新通常 5 分钟内生效，可手动加 `?t=时间戳` 强制刷新

**assets 目录保留**：存放原始 PNG 文件，便于更新时重新提取 base64 上传 Gitee。

**品牌位 Logo**（右下角）：使用 `yonsuite-logo.png`，通过 `brand-footer` 的 CSS `background` 或 `img` 引入。
## 字体规范（Typography Rules）

**统一字体：微软雅黑。禁止斜体、下划线、艺术体。**

**字号有两套标准，根据使用场景选择：**

### A. 网页阅读级（默认，适合屏幕近距离阅读）

| 层级 | 字号 | 样式 | 颜色 |
|------|------|------|------|
| 大标题 | 24-28px | 微软雅黑加粗 | 红色 #E60012 |
| 副标题 | 18-22px | 微软雅黑加粗 | 深灰 #3B3838（重点词可标红） |
| 正文 | ≤14px | 微软雅黑常规 | 深灰 #3B3838 |
| 注释/来源 | 10-12px | 微软雅黑常规 | 浅灰 #717071 |

### B. 投影/PPT级（当用户说"当PPT用"、"投影看不清"、"字太小"时，直接切到此标准）

> ⚠️ **触发词：** "当 PPT 用" / "投影" / "字太小了根本看不清" / "大胆调大"
> ⚠️ **此标准为强制覆盖**——一旦触发，不要从网页级逐级上调，直接跳到投影级基准。

| 层级 | 字号 | 样式 | 说明 |
|------|------|------|------|
| 封面主标题 | 48-56px | 微软雅黑加粗 | 深灰/红色 |
| 章节标题 (section-title) | 32-34px | 微软雅黑加粗 | #3B3838 |
| 章节副标题 (section-sub) | 20-22px | 微软雅黑常规 | #717071 |
| 卡片标题 | 18-22px | 微软雅黑加粗 | 按场景配色 |
| 正文 / 描述文字 | 16-19px | 微软雅黑常规，可加 font-weight:500 | 深灰/灰色 |
| 标签 (tag) | 13-14px | 微软雅黑加粗 | 按场景配色 |
| 辅助 / 脚注 | 13-15px | 微软雅黑常规 | 浅灰 |
| 页面编号 | 38-42px | Arial加粗 | 红色 |

### 投影级布局参数

| 参数 | 网页级 | 投影级 |
|------|--------|--------|
| 内容区顶部 padding (page-header) | 70-95px | **145px** |
| 卡片内边距 | 14-18px | **24-30px** |
| 三列卡片间距 (grid-gap) | 14-16px | **28-32px** |
| 四列卡片间距 | 12-14px | **22-28px** |
| 卡片圆角 (border-radius) | 8-10px | **12-14px** |
| 子区块内边距 | 8-12px | **16-22px** |

### 投影级字号调整方法

当需要把已有网页级 HTML 调整到投影级时，**不要逐行手动改**。用全局 font-size 映射批量替换：

```
网页级 → 投影级映射（一档跳到位，不逐级上调）：
10px→14px  11px→15px  12px→16px  13px→17px  14px→18px
15px→19px  16px→20px  17px→21px  18px→22px  20px→24px
24px→28px  28px→32px  32px→36px  44px→48px  48px→56px
```

**调整顺序（每次都要按此流程）：**
1. 先用全局 font-size 映射批量替换所有内联字号
2. 再调 CSS 类的字号（section-title / section-sub / tag 等）
3. 然后批量增大 gap（+8~10px）和 padding（+6~12px）
4. 最后把 page-header padding-top 调到 140-145px
5. 特殊元素单独手动微调（封面主标题、结束页、重点内容区如"核心痛点"）

> **预期迭代：** 通常需要 2-4 轮才能完全对齐用户预期——第一轮调字号，第二轮调间距，第三轮调特殊元素，第四轮用户确认。不要试图一轮到位。

### 导航按钮（投影场景）

投影/PPT 场景下导航按钮要**缩小隐藏**，用键盘翻页为主，鼠标为辅：

```css
.ctrl { bottom: 10px; left: 50%; transform: translateX(-50%); gap: 4px; }
.ctrl button {
  background: transparent;
  border: 1px solid rgba(0,0,0,.08);
  border-radius: 4px;
  padding: 3px 10px; font-size: 10px;
  color: #A0A0A0;
  transition: all .2s;
}
.ctrl button:hover {
  color: #717071;
  border-color: rgba(0,0,0,.15);
  background: rgba(0,0,0,.03);
}
```

按钮逻辑：默认透明浅灰色，hover 时微微加深。用户主要通过键盘← →或滚轮翻页，按钮只在需要鼠标操作时可见。网页阅读场景保留正常大小按钮。

### 行间距

- 正文：1.2-1.5 倍
- 标题：1.0 倍
- 条目化内容：可调整为 2.0 倍
- 整体原则：避免文字拥挤或松散

### 禁止使用

- 斜体
- 艺术字
### 颜色规范

- 正文：灰色 `#717071`
- 强调文字：用友红 `#E60012`
- 注释/来源：浅灰 `#717071`

## 配色规范（Color Rules）

**视觉认知的"记忆锚点"：固定的品牌主色和辅助色让所有 PPT 带有统一视觉印记，加深品牌记忆；通过配色区分重点与辅助信息，引导视觉焦点，让观众注意力自然流向核心观点，提升信息接收效率。**

### 品牌主色（红白灰）

| 颜色 | 色值 | 用途 |
|------|------|------|
| 红色 | #E60012 | 标题、强调内容、按钮 |
| 白色 | #FFFFFF | 深色背景上的文字、表格背景、框架图色块 |
| 灰色 | #717071 | 正文、注释文字 |

### 色调占比

- 灰色：正文内容、图表等大部分元素用灰色表达
- 红色：强调重点，**占比不超过 20%**

### 渐变规则

- **仅在箭头上使用红白渐变**
- 灰色可以渐变

### 禁用规则

- 大面积竞争对手品牌色（如：金蝶蓝）
- 高饱和度撞色：红配绿、黄配紫等高冲突配色
- 低对比度组合：浅灰底配浅灰字等低对比度组合

### 图表配色

- 同一类图表配色保持统一
- 色调不超过 3 个
- 例如架构图：灰、白色作为框架底色，红色用于强调的内容

## 布局规范（Layout Rules）

**信息逻辑的"导航地图"：好的页面布局和排版能够建立视觉秩序，统一的网格对齐和留白规则让页面元素排列更有序，观众能顺着视觉流快速理解内容逻辑，同时保障 PPT 的专业质感。**

### 网格与页边距

- 开启对齐参考线
- 标题区：页边距 13%
- 页脚区：页边距 6%
- 左右间距：4%
- 所有元素对齐网格

### 对齐规则

- 正文：统一左对齐
- 标题：统一居中对齐
- **禁止**：一页内混合多种对齐方式

### 留白原则

- 页面四周、内容布局之间、文字与边框之间留空隙，避免信息堆砌
- 页面留白占比 ≥ 30%
- 模块之间保持 25-40pt 间距

### 图表规则

- 图表中同组元件高度一致，间距相等

### 图片规范

- 分辨率 ≥ 300dpi
- 统一添加 0.5pt 浅灰边框
- 禁止拉伸变形
- 风格保持一致（全用实景图或全用扁平插图）

### 禁止事项

- 排版混乱、元素歪斜
- 留白不足、页面拥挤
- 内容块之间无间距
- 同一页混合多种对齐方式

## 内容规范（Content Rules）

**观点表达的"精准武器"：根据"一页一主题"规则，聚焦核心内容，避免大段文字堆砌，让每一页的观点清晰有力；正文用"短句 + 要点"让观众更容易抓住重点，或通过图表/架构图更具逻辑性。**

### 一页一主题

- 每页只讲一个核心观点，标题直接点题

### 内容层次

- 遵循"标题 → 核心内容 → 辅助信息"的视觉流
- 层次清晰

### 条目列举

- 正文用"短句 + 要点"
- 避免大段文字的信息堆砌

### 重点突出

- 重要内容用加粗、色块或图标突出

### 图表规则

- 可采用图表、架构图等
- 展现对比、逻辑性的内容

### 图标统一

- icon 等图标统一（可参考 PPT 素材或阿里图标库的线性图标）
- 风格、色调、尺寸保持一致

### 禁止事项

- 大段文字堆砌，无重点
- 页面信息过载
- 辅助信息占比过高，干扰核心观点

### 推荐形式

- "标题 + 辅助信息"
- "短句 + 要点"

### 页眉页脚

- 统一使用母版设置
- 页眉：公司 Logo
- 位置固定

### 推荐形式

- "标题 + 辅助信息"
- "短句 + 要点"

### 页眉页脚

- 统一使用母版设置
- 页眉：公司 Logo
- 位置固定


### YonSuite 官方设计共性规则（白底方案专用）

## 通用布局规则（白底方案）

| 维度 | 规则 |
|------|------|
| **品牌位** | 右下角固定放品牌 Logo 或 Slogan |
| **三色点缀** | 标题下方或左上角用红/橙/蓝三色短线段或渐变色块 |
| **几何装饰** | 抽象几何切片、圆点、箭头点缀（参考用友官方PPT） |
| **圆角** | 所有元素用大圆角（border-radius: 12-20px） |
| **图标** | 扁平或伪3D玻璃拟态，圆形底托，色彩丰富但统一 |
| **背景纹理** | 淡灰网格/点阵/波浪纹理，增加细节不抢眼 |
| **渐变** | 标题下划线、图标内部用蓝→紫或橙→红渐变 |
| **字体** | 无衬线粗标题 + 细正文，层级清晰 |
| **留白** | 大量留白，页面四周、内容布局之间、文字与边框之间要留空隙，呼吸感强 |

## Page Structure

**HTML 层级结构（必须严格遵守）：**

```
body
├── <button class="fs-btn">          ← 全屏按钮（body-level fixed）
├── <img class="page-logo">          ← 左上角 Logo（body-level fixed）
├── <div class="step-dots">         ← 右上角步骤圆点（body-level fixed）
├── <div class="page-indicator">     ← 底部页码圆点（body-level fixed）
├── <div class="brand-footer">      ← 右下角品牌位（body-level fixed）
├── <div class="slides-wrapper">    ← 翻页容器（会做 translateX）
│   ├── <div class="slide">       ← 第1页
│   ├── <div class="slide">       ← 第2页
│   └── ...
└── <script>                       ← 翻页逻辑
```

**关键原则：所有 Fixed UI 元素（logo/step-dots/brand-footer/page-indicator）必须放在 slides-wrapper 外面、body 层级。绝对不能放在 slide 内部或 slides-wrapper 内部。**

原因：`position: fixed` 元素的包含块是 initial containing block（视口），不受 transform 影响。但如果 fixed 元素的父祖先有 `transform`（如 slides-wrapper 的 translateX），则 fixed 会相对于那个祖先定位，导致翻页时位置错误。

**slides-wrapper 只包含各 slide div，不包含任何 fixed 元素。**

## Slide Types

### 1. Hero Slide（封面/首页）

**白底+背景图版本（左右分栏，左侧文字右侧图）：**
**注意：logo/step-dots/page-indicator/brand-footer 已移到 body-level fixed，不再写在 slide 内部。**
```html
<div class="slide slide-hero">
  <!-- 背景图 -->
  <div class="hero-bg" style="..."></div>

  <!-- 左侧文字区 -->
  <div class="hero-text">
    <div class="eyebrow">YonSuite · 企业数智化平台</div>
    <h1>集团管控<br>解决方案</h1>
    <div class="title-bar">
      <span class="bar-red"></span>
      <span class="bar-orange"></span>
      <span class="bar-blue"></span>
    </div>
    ...
  </div>
</div>
```

```css
.slide-hero { position: relative; overflow: hidden; background: white; }
.hero-bg {
  position: absolute; top: 0; right: 0; bottom: 0; left: 45%;
}
.hero-text {
  position: absolute; left: 6%; top: 50%;
  transform: translateY(-50%);
  z-index: 10;
}
.hero-meta {
  margin-top: 32px; font-size: 15px; color: #86868B;
}
.meta-sep { margin: 0 12px; color: #D2D2D7; }
.title-bar { display: flex; gap: 6px; margin: 16px 0; }
.title-bar span { display: block; height: 4px; width: 32px; border-radius: 2px; }
.bar-red { background: #E60012; }
.bar-orange { background: #FF6B00; }
.bar-blue { background: #0071E3; }
```

### 2. Pain/Solution（双栏对比）
- 左栏：传统方案（深灰背景）
- 右栏：解决方案（标准背景）
- 每个要点配 `✓` 或 `–` 图标

### 3. Feature Cards（能力网格）
- 4列/5列网格布局
- 每卡片：图标 + 编号标签 + 标题 + 描述
- 悬浮效果：背景变蓝 + 上浮 + 顶部光条

### 4. Architecture（架构图）
- 层级方块：集团总部（蓝底）→ 子公司（灰底）→ 业务组织（更灰）
- 带箭头连接符

### 5. Scenarios（场景）
- 2×2 网格
- 每场景：左侧图标色块 + 编号 + 标题 + 描述

### 6. YonSuite 能力总览（白底卡片风）
- 白色背景，2×3 六宫格布局
- 每个卡片：圆形伪3D图标 + 标题框（圆角渐变底） + 正文
- 底部右下角品牌 Logo + Slogan
- 卡片容器：浅灰虚线边框或淡背景色
- 参考：三色点缀短线段作为标题装饰

### 7. End Slide（结束页/致谢页）

参考图：`assets/end-slide-ref.png`
```html
<div class="slide slide-end">
  <div class="end-bg" style="background:url('assets/end-slide-ref.png') right center/60% auto no-repeat white;"></div>

  <!-- 右上角圆点序列 -->
  <div class="step-dots">
    <div class="step-dot"></div>
    <div class="step-dot"></div>
    <div class="step-dot active"></div>
  </div>

  <!-- 左侧文字区 -->
  <div class="end-text">
    <div class="end-slogan">
      <span class="slogan-bracket">&#91;</span>
      <span class="slogan-main">智领全球</span>
      <span class="slogan-sep"> </span>
      <span class="slogan-red">共赢BIP</span>
      <span class="slogan-bracket">&#93;</span>
    </div>
    <h2 class="end-title">谢谢观看</h2>
    <p class="end-subtitle">THANK YOU</p>
  </div>

  <!-- 底部品牌位 -->
  <div class="brand-footer">
    <img src="data:image/png;base64,iVBORw0KGgoAAA..." class="brand-logo-img" alt="YonSuite">
    <span>成长型企业就用YonSuite</span>
  </div>
</div>
```
```css
.slide-end { position: relative; overflow: hidden; background: white; }
.end-bg {
  position: absolute; top: 0; right: 0; bottom: 0;
  /* 背景图占右侧60% */
}
.end-text {
  position: absolute; left: 8%; top: 50%;
  transform: translateY(-50%);
  z-index: 10;
}
.end-slogan {
  font-size: 13px; letter-spacing: 0.1em; color: #86868B;
  margin-bottom: 24px; font-weight: 500;
}
.slogan-bracket { color: #86868B; margin: 0 4px; }
.slogan-main { color: #86868B; }
.slogan-sep { display: inline-block; width: 8px; }
.slogan-red { color: #E60012; }
.end-title {
  font-size: 72px; font-weight: 700;
  letter-spacing: -0.02em; color: #1D1D1F;
  margin-bottom: 8px;
}
.end-subtitle {
  font-size: 18px; letter-spacing: 0.3em;
  color: #86868B; font-weight: 500;
}
```

## Logo 规范（重要·每页统一）

**核心原则：除首页、尾页之外的每一页，左上角都必须有 logo，且全程保持一致。**

### 目录结构

```
assets/
  logo/
    current-logo.png    ← 当前使用的 logo（公子放入素材后我会更新这个）
    logo-001.png       ← 公子提供的第 N 个 logo 素材
    logo-002.png
    ...
  topleft-logo.png     ← 左上角装饰用（老文件，可保留参考）
  yonsuite-logo.png    ← 右下角品牌位用
```

### 各页 logo 规则

| 页类型 | 左上角 logo | 右下角品牌位 |
|--------|------------|-------------|
| 首页（slide-1） | ✓ 有 | ✓ 有 |
| 尾页（slide-N） | ✓ 有 | ✓ 有 |
| 中间页（slide-2 ~ slide-N-1） | ✓ **必须有**，与首尾页一致 | 可选，一般也保留 |

### CSS 规范

```css
/* 左上角 logo（所有页面通用） */
.page-logo {
  position: fixed;
  top: 24px;
  left: 32px;
  height: 28px;   /* 统一高度，可视情况小幅调整 */
  z-index: 100;
  opacity: 0.8;   /* 不抢内容但存在感足够 */
}

/* 非首页尾页：左上角 logo 优先显示 */
.slide:not(.slide-hero):not(.slide-end) .page-logo {
  display: block;
}
```

### 使用方式（HTML）

```html
<!-- 每页都统一加这个 img，建议放在 .slide 内最顶部 -->
<img src="assets/logo/current-logo.png" class="page-logo" alt="Logo">

<!-- 首页特殊：左上角 logo 依然保留，位置与其他页一致 -->
<div class="slide slide-hero">
  <img src="assets/logo/current-logo.png" class="page-logo" alt="Logo">
  ...
</div>
```

### 素材更新流程

1. 公子把新 logo 素材放入 `assets/logo/` 目录
2. 命名规范：`logo-序号.png`（如 `logo-003.png`）
3. 我收到后，将 `assets/logo/current-logo.png` **同步更新为最新版本**
4. 后续所有页面自动引用新 logo，无需逐页修改

> 当前 logo：`assets/logo/current-logo.png`（首次初始化时从现有 `topleft-logo.png` 复制一份作为起点）

## Brand Footer（品牌位）

右下角固定品牌区（**使用 base64 嵌入，不依赖外部文件**）：
```html
<div class="brand-footer">
  <img src="data:image/png;base64,iVBORw0KGgoAAA..." class="brand-logo-img" alt="YonSuite">
  <span>成长型企业就用YonSuite</span>
</div>
```
```css
.brand-footer {
  position: fixed; bottom: 20px; right: 32px;
  display: flex; align-items: center; gap: 10px;
  font-size: 12px; color: var(--text-sub);
  z-index: 100;
}
.brand-logo-img {
  height: 20px; /* 保持比例 */
  opacity: 0.7;
}
```

> Logo 文件：`skills/yonyou-html-presentation/assets/yonsuite-logo.png`（生成 HTML 时转换为 base64 嵌入）

## Decorative Elements（装饰元素）


### 三色短线段（标题装饰）
```css
.hero-divider {
  width: 48px; height: 3px;
  background: linear-gradient(90deg, #E60012, #FF6B00, #0071E3);
  border-radius: 2px; margin: 20px 0;
}
```

### 几何装饰切片（左上角）
```css
.slice-decor {
  position: absolute; top: 0; left: 0;
  width: 120px; height: 120px;
  background: linear-gradient(135deg, rgba(230,0,18,0.08), transparent);
  clip-path: polygon(0 0, 100% 0, 0 100%);
}
```

### 网格纹理背景（底部）
```css
.grid-bg {
  background-image:
    radial-gradient(circle, rgba(0,0,0,0.06) 1px, transparent 1px);
  background-size: 24px 24px;
}
```

### 右上角圆点序列（页码/步骤指示）
```css
.step-dots {
  position: fixed; top: 24px; right: 32px;
  display: flex; align-items: center; gap: 6px;
  z-index: 100;
}
.step-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: #E60012; /* 可调透明度实现渐变淡出 */
}
.step-dot:nth-child(1) { opacity: 1; }
.step-dot:nth-child(2) { opacity: 0.6; }
.step-dot:nth-child(3) { opacity: 0.3; }
.step-dot:nth-child(4) { opacity: 0.1; }
/* 激活状态（当前页）：实色 + 略大 */
.step-dot.active {
  width: 10px; height: 10px;
  background: #E60012;
  opacity: 1;
  box-shadow: 0 0 6px rgba(230,0,18,0.4);
}
```

> 也可与底部圆点导航（pageIndicator）二选一使用

### 左上角品牌Logo
```css
.top-left-logo {
  position: fixed; top: 24px; left: 32px;
  height: 24px; z-index: 100;
  opacity: 0.75;
}
```
```css
.dashed-card {
  border: 1.5px dashed rgba(0,0,0,0.12);
  border-radius: 16px;
  background: rgba(245,245,247,0.6);
}
```

## Lucide Icons（图标系统）

### 图标来源

使用 **Lucide** 图标库（`ui-ux-pro-max` skill 的 `data/icons.csv` 收录了 100 个预制图标）。

### 查询工具

内置图标查询脚本：`scripts/lucide_icon_lookup.py`

```bash
# 搜索图标（按名称/关键词/分类）
python3 scripts/lucide_icon_lookup.py search cloud
python3 scripts/lucide_icon_lookup.py search 购物

# 获取指定图标的 SVG 代码
python3 scripts/lucide_icon_lookup.py get arrow-right

# 列出某分类所有图标
python3 scripts/lucide_icon_lookup.py list Action
python3 scripts/lucide_icon_lookup.py list Commerce

# 随机推荐一个适合 PPT 的图标
python3 scripts/lucide_icon_lookup.py random
```

### 使用方式（两种）

**方式 A：inline SVG（推荐，零依赖、单文件可离线）**

```python
from scripts.lucide_icon_lookup import get_svg
# 在生成 HTML 时直接调用
svg_tag = get_svg("arrow-right", size=20, stroke="#E60012")
```

输出格式：
```html
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"
  viewBox="0 0 24 24" fill="none" stroke="#E60012"
  stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
  class="icon icon-arrow-right">
  <path d="M5 12h14m-7-7 7 7-7 7"/>
</svg>
```

> ⚠️ **参数名是 `stroke`，不是 `color`**。函数签名：`get_svg(name, size=24, stroke="currentColor", stroke_width=2)`

**方式 B：CDN + data-lucide（需网络，图标最全）**

```html
<script src="https://unpkg.com/lucide@latest"></script>

<!-- 在 HTML 中用 data-lucide 属性声明图标 -->
<i data-lucide="arrow-right" class="icon-arrow"></i>

<!-- 初始化（通常放 body 末尾） -->
<script>lucide.createIcons();</script>
```

### 常用图标与场景对应

| 场景 | 推荐图标 | 说明 |
|------|---------|------|
| 导航/前进 | `arrow-right` | CTA 按钮、步骤指引 |
| 返回/后退 | `arrow-left` | 返回按钮 |
| 增/建/添加 | `plus` | 新建项目、新增数据 |
| 删除/移除 | `trash-2` | 删除操作（注意：数据报告不用图标，用颜色区分） |
| 编辑/修改 | `edit` | 编辑入口 |
| 保存/提交 | `save` | 保存按钮 |
| 下载/导出 | `download` | 导出功能 |
| 上传/导入 | `upload` | 导入功能 |
| 搜索 | `search` | 搜索框 |
| 筛选/过滤 | `filter` | 筛选器 |
| 成功/完成 | `check-circle` | 状态标记 |
| 警告/注意 | `alert-triangle` | 警示状态 |
| 错误/失败 | `x-circle` | 错误状态 |
| 信息/提示 | `info` | 信息提示 |
| 购物/订单 | `shopping-cart` | 电商、订单场景 |
| 支付/金额 | `credit-card` | 支付、账单 |
| 数据/分析 | `bar-chart` | 数据分析页 |
| 趋势/增长 | `trending-up` | 增长、上升趋势 |
| 用户/会员 | `user` | 用户管理 |
| 团队/协作 | `users` | 多人协作 |
| 安全/合规 | `shield-check` | 安全、合规审批 |
| 锁/权限 | `lock` | 权限控制 |
| 文件/档案 | `file-text` | 文档、报表 |
| 文件夹/归档 | `folder` | 档案管理 |
| 日历/计划 | `calendar` | 日程、计划 |
| 邮件/通知 | `mail` | 通知、邮件 |
| 设置/配置 | `settings` | 系统配置 |
| 全球/多语言 | `globe` | 全球化、多币种 |
| AI/智能化 | `cpu` 或 `zap` | 智能化特性 |
| 组织/架构 | `building` | 组织架构 |
| 供应链 | `truck` | 采购、物流 |

### 图标名称兼容性（重要 Pitfall）

> ⚠️ `scripts/lucide_icon_lookup.py` 的内置图标池并非 Lucide 全量，以下常用名称会返回 HTML 注释占位符（如 `<!-- 图标 'bar-chart-3' 未收录，请补充 -->`）：

| 常用名（缺失） | 替换为（可用） |
|---|---|
| `bar-chart-3` | `bar-chart` |
| `message-square` | `message-circle` |
| `code-2` | `code` |
| `brain` | `cpu` 或 `lightbulb` |
| `check-circle-2` | `check-circle` |

**生成前验证：** 所有用到的图标先用 `get_svg(name)` 测试，检查返回值是否包含 `<svg` 标签且长度 > 50 字符。如果返回 HTML 注释占位符，立即切换到上表的替换名。

### 图标使用规范

- **统一风格**：全部使用 Lucide Outline 线性风格（stroke-width=2）
- **统一尺寸**：能力卡片用 20-24px，正文图标用 16-18px
- **统一颜色**：品牌红 `#E60012` 用于强调，品牌灰 `#717071` 用于辅助
- **禁止填充**：不用填充型图标，保持线条简洁
- **颜色映射**：
  - 红色系：`#E60012` → 重点强调
  - 蓝色系：`#0071E3` → 链接、可点击
  - 灰色系：`#717071` → 辅助信息、不活跃状态

### 内置 SVG 图标池

`scripts/lucide_icon_lookup.py` 已内置 80+ 常用图标的 path 数据，生成 HTML 时无需联网即可直接使用。查询结果中的 `get_svg()` 函数返回完整 SVG 标签，可直接写入 HTML。

## Tech Effects（可选增强）

### Canvas 粒子动画背景
```javascript
(function(){
  const canvas = document.getElementById('techCanvas');
  const ctx = canvas.getContext('2d');
  let W, H, particles = [];
  // 50个粒子 + 连线效果
  // 背景细网格
  function animate() {
    ctx.clearRect(0,0,W,H);
    drawGrid(); drawLines();
    particles.forEach(p => { p.update(); p.draw(); });
    requestAnimationFrame(animate);
  }
  animate();
})();
```

### 悬浮发光效果
```css
.feat-card:hover {
  background: rgba(0,113,227,0.09);
  transform: scale(1.02);
  box-shadow: 0 8px 40px rgba(0,113,227,0.18);
}
```

## Navigation

```javascript
const total = 5; // 总页数
let current = 0;

// 键盘
document.addEventListener('keydown', e => {
  if (e.key === 'ArrowRight' || e.key === ' ') goTo(current + 1);
  if (e.key === 'ArrowLeft') goTo(current - 1);
});

// 触摸
let touchStartX = 0;
document.addEventListener('touchend', e => {
  const dx = e.changedTouches[0].clientX - touchStartX;
  if (Math.abs(dx) > 50) dx < 0 ? goTo(current+1) : goTo(current-1);
});

// 全屏
function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen();
  } else {
    document.exitFullscreen();
  }
}
```

## Output & Delivery

**文件发送**：通过 `message` 工具发送，不要 `open` 本地查看（飞书频道需求产生的文件走飞书发送流程）。

**文件路径**：默认保存到 `~/Documents/` 下的分类目录（如 `~/Documents/YonSuite/`）。

## Design Checklist

发布前检查：
- [ ] 字体大小适合使用场景（网页阅读级按网页标准，投影/PPT级按投影级标准）
- [ ] 投影级：章节标题 ≥ 32px，正文 ≥ 16px，page-header padding-top ≥ 140px
- [ ] 深浅页配色统一，不跳变
- [ ] 圆点/按钮导航正常
- [ ] 键盘左右翻页正常
- [ ] 全屏模式正常
- [ ] 全屏按钮位于左下角（bottom: 24px; left: 32px）
- [ ] 无 emoji（用 SVG 图标替代）
- [ ] 蓝色链接/强调色一致

**YonSuite 白底方案额外检查：**
- [ ] 右下角品牌位（Logo + Slogan）
- [ ] 标题下方三色短线段或渐变装饰
- [ ] 卡片虚线边框或淡背景
- [ ] 底部网格/点阵纹理（如适用）
- [ ] 圆角统一（border-radius: 12-20px）

## Convention Maintenance（规范维护）

**重要原则**：在使用 skill 过程中，对样式规范、交互规则、输出路径等所做的任何调整，必须主动记录到所属 skill 文档的对应章节中，形成闭环。

常见需要记录的调整：
- 样式规则（如全屏按钮位置、字体大小规范、配色调整）
- 输出路径规范（如 `~/Documents/` 下的子目录结构）
- 交互规则（如翻页方式、导航位置）
- 内容整理流程（如采集方法、页数规划）
- 任何在执行过程中发现并修正的遗漏规则

记录时机：调整完成后立即记录，不要等到任务结束。

**被追问改正时的标准（来自公子纠正，2026-04-27）：**
- ✅ 给出**具体可执行方案**，说清具体怎么做
- ❌ 不能只认错、不改进
- 规矩：①开口前自检，没核实不猜 ②语气软 ③被追问改正说清具体怎么做

## Workflow

### 步骤 0：信息采集（关键前置步骤，信息不足不动手）

> ⚠️ **铁律：信息不齐不动工。** 用友产品相关内容必须"先搜知识库、再补联网"，拿到足够信息后才开始规划页面。

#### 信息采集优先级

| 优先级 | 来源 | 工具 | 场景 |
|--------|------|------|------|
| **1. Obsidian 知识库** | `~/Documents/zuoxiaojunWiki/` | `obsidian-cli` | 用友产品、案例、概念、AI 能力等结构化知识 |
| **2. YonSuite 官网文案** | 技能内置 `assets/yonsuite-official-content.md` | 直接读取 | 品牌定位、十大领域描述、AI 能力列表 |
| **3. 联网补充** | 用友官网、新闻、行业报告 | `web_search` + `web_extract` | 最新动态、市场数据、新增功能（知识库没覆盖的） |

#### Obsidian 知识库搜索（优先使用 obsidian-cli）

```bash
# Obsidian 必须正在运行
obsidian vault="zuoxiaojunWiki" search query="关键词1 关键词2" limit=10
obsidian vault="zuoxiaojunWiki" tags counts              # 了解知识结构
obsidian vault="zuoxiaojunWiki" read file="笔记名称"     # 读取具体笔记
obsidian vault="zuoxiaojunWiki" backlinks file="笔记名称" # 找关联内容
```

> 如果 Obsidian 没运行或 `obsidian-cli` 不可用，fallback 到 `obsidian` skill 的 `grep -rli` 方式。

#### 联网补充搜索

```bash
# 知识库覆盖不足时，补充联网搜索
web_search query="YonSuite 一体化 最新功能 2026"
web_search query="用友 AI 智能体 企业应用"
```

#### 确认清单（满足后才进入步骤 1）

- [ ] Obsidian 知识库已搜索，提取了核心概念和数据
- [ ] 需要的内容（产品能力、案例、数据）至少有 2 个来源交叉验证
- [ ] 标题/副标题、各页核心内容、数据支撑已整理完毕
- [ ] 页数和内容块结构已确认

### 步骤 1-5：制作与交付

1. **框架搭建**：写 HTML 结构 + 基础 CSS，先确定场景是网页阅读还是投影/PPT
2. **设计落地**：按配色/字体/间距规范执行——投影场景直接用投影级标准，不要从网页级一步步上调
3. **细节装饰**：SVG 图标、悬浮效果、粒子背景（可选）
4. **字号调整**：投影场景按「投影级字号调整方法」批量映射 + gap/padding 同步放大
5. **交互测试**：全屏、翻页、触摸滑动，发布前过 Design Checklist
