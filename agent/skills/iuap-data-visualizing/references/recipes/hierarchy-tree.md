# 层级树状图（Tree Chart — 纯 HTML/CSS）

> 展示有明确父子关系的层级数据（如企业产权、组织架构、分类体系），支持自定义卡片、连线标注和折叠交互。

**实现方式**：纯 HTML/CSS/JS，**不使用 ECharts**。原因：ECharts tree 对节点卡片样式自定义能力有限，纯 CSS 方案可完全控制卡片布局、连线样式和交互行为。

### 核心技术点

| 技术点 | 方案 | 关键 CSS |
| -------- | ------ | ---------- |
| 树形布局 | `ul/li` 嵌套 + `display: flex` | `li { flex-direction: column; align-items: center }` |
| 垂直连线（父→子） | `ul::before` 伪元素 | `border-left: 2px solid` |
| 水平横杆（兄弟间） | `li::before` + `li::after` | `border-top: 2px solid` |
| 垂直分支（横杆→子卡） | 同上伪元素的 `border-right/left` | 配合 `width: 50%` |
| 折叠按钮 | `<span class="toggle-btn">` | `::before` 画横线（−），`collapsed::after` 画竖线（+） |
| 卡片样式 | 圆角 + 阴影 + hover 上浮 | `box-shadow`, `transform: translateY(-3px)` |
| 连线标注 | `position: absolute` 定位在分支线上 | 彩色 method-tag + 比例数字 |
| 自适应缩放 | `transform: scale()` + `autoFit` | 根据视口宽度自动调整 |

### 完整 CSS 连线系统

```css
:root {
  --c-type1: #2B6CB0;
  --c-type2: #C05621;
  --c-type3: #2F855A;
  --bg-root: #EBF4FF;
  --bg-node: #FFFFFF;
  --line-color: #94A3B8;
  --line-width: 2px;
  --connector-h: 44px;
  --shadow: 0 4px 16px rgba(0,0,0,0.08);
}

/* 树形布局 */
.tree ul {
  display: flex; justify-content: center;
  position: relative; list-style: none;
  padding: 0; margin: 0;
}
.tree ul ul { padding-top: var(--connector-h); }
.tree ul ul::before {
  content: '';
  position: absolute;
  top: 0; left: 50%;
  width: 0; height: var(--connector-h);
  border-left: var(--line-width) solid var(--line-color);
}
.tree li {
  display: flex; flex-direction: column; align-items: center;
  position: relative; padding: 0 14px;
}
.tree ul ul > li { padding-top: var(--connector-h); }
.tree ul ul > li::before,
.tree ul ul > li::after {
  content: '';
  position: absolute;
  top: 0; width: 50%; height: var(--connector-h);
}
.tree ul ul > li::before {
  right: 50%;
  border-right: var(--line-width) solid var(--line-color);
  border-top: var(--line-width) solid var(--line-color);
}
.tree ul ul > li::after {
  left: 50%;
  border-left: var(--line-width) solid var(--line-color);
  border-top: var(--line-width) solid var(--line-color);
}
.tree ul ul > li:first-child::before { border-top: none; }
.tree ul ul > li:last-child::after { border-top: none; }
.tree ul ul > li:only-child::after { border-left: none; border-top: none; }
.tree ul ul > li:only-child::before { border-top: none; }
.tree > ul > li { padding-top: 0; }
.tree > ul > li::before,
.tree > ul > li::after { display: none; }
```

### 节点卡片样式

```css
.node-card {
  position: relative; z-index: 2;
  width: 180px; background: var(--bg-node);
  border-radius: 10px; box-shadow: var(--shadow);
  border: 1px solid #E2E8F0; overflow: hidden;
  transition: transform 0.2s, box-shadow 0.2s;
}
.node-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
}
.node-card.root {
  width: 200px;
  background: var(--bg-root);
  border: 2px solid var(--c-type1);
}
.card-header {
  display: flex; justify-content: center; align-items: center;
  padding: 10px 12px 8px;
}
.card-header .name {
  font-size: 13px; font-weight: 700; color: #fff;
  padding: 4px 16px; border-radius: 12px;
  text-align: center;
}
.card-body { padding: 2px 12px 10px; }
.card-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 3px 0; font-size: 12px;
  border-top: 1px solid #F1F5F9;
}
.card-row .label { color: #94A3B8; }
.card-row .value { color: #334155; font-weight: 500; }
```

### 连线标签

```css
.edge-label {
  position: absolute;
  top: 10px; left: 50%;
  transform: translateX(-50%);
  z-index: 3;
  display: flex; align-items: center; gap: 5px;
  background: #fff;
  border: 1px solid #E2E8F0;
  border-radius: 12px;
  padding: 2px 6px 2px 2px;
  white-space: nowrap;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
.method-tag {
  display: inline-block;
  padding: 1px 8px; border-radius: 10px;
  font-size: 11px; font-weight: 600; color: #fff;
}
.ratio-text { font-size: 11px; font-weight: 600; color: #475569; }
```

### 折叠交互

```css
.toggle-btn {
  position: relative; z-index: 4;
  width: 20px; height: 20px; margin-top: 2px;
  border: 2px solid var(--line-color); border-radius: 50%;
  background: #fff; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 1px 4px rgba(0,0,0,0.1);
  transition: all 0.25s ease; user-select: none;
}
.toggle-btn::before {
  content: ''; display: block;
  width: 10px; height: 2px; background: #64748B;
}
.toggle-btn.collapsed::after {
  content: ''; position: absolute;
  width: 2px; height: 10px; background: #64748B;
}
li.collapsed > ul { display: none !important; }

.child-count {
  position: absolute; top: -7px; right: -8px;
  background: #64748B; color: #fff;
  font-size: 9px; font-weight: 700;
  min-width: 14px; height: 14px;
  border-radius: 7px;
  display: flex; align-items: center; justify-content: center;
  padding: 0 3px;
}
```

### 自适应缩放

```javascript
let scale = 1;
const treeEl = document.querySelector('.tree');
const wrapperEl = document.querySelector('.tree-wrapper');

function autoFit() {
  const treeWidth = treeEl.scrollWidth;
  const viewWidth = wrapperEl.clientWidth;
  if (treeWidth > viewWidth) {
    scale = Math.max(0.4, viewWidth / treeWidth);
  } else {
    scale = 1;
  }
  treeEl.style.transform = `scale(${scale})`;
  treeEl.style.transformOrigin = 'top center';
}

function zoomIn() {
  scale = Math.min(scale + 0.1, 2);
  treeEl.style.transform = `scale(${scale})`;
  treeEl.style.transformOrigin = 'top center';
}

function zoomOut() {
  scale = Math.max(scale - 0.1, 0.3);
  treeEl.style.transform = `scale(${scale})`;
  treeEl.style.transformOrigin = 'top center';
}

function resetZoom() {
  scale = 1;
  treeEl.style.transform = 'scale(1)';
}

window.addEventListener('load', autoFit);
window.addEventListener('resize', autoFit);
```

### 踩坑记录

| 问题 | 原因 | 解决 |
| ------ | ------ | ------ |
| 根节点出现多余连线 | 根 `li` 的伪元素未清除 | `.tree > ul > li::before/::after { display: none }` |
| 折叠后连线残留 | `ul::before` 未随 `ul` 隐藏 | `li.collapsed > ul { display: none !important }` |
| only-child 双竖线 | `::before` 和 `::after` 各画一条 | `only-child::after { border-left: none }` |
| 深层节点溢出视口 | 树宽超出容器 | `autoFit` 自动缩放 + `overflow: auto` 支持滚动 |

### 完整 HTML 示例

以下是可运行的完整 HTML 模板，包含所有 CSS 样式、HTML 结构和 JavaScript 交互：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>产权关系树图</title>
  <style>
    :root {
      --c-quanzi: #2B6CB0;
      --c-konggu: #C05621;
      --c-lianying: #2F855A;
      --bg-root: #EBF4FF;
      --bg-node: #FFFFFF;
      --line-color: #94A3B8;
      --line-width: 2px;
      --connector-h: 44px;
      --shadow: 0 4px 16px rgba(0,0,0,0.08);
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Microsoft YaHei', 'PingFang SC', -apple-system, sans-serif;
      background: linear-gradient(160deg, #EDF2F7 0%, #E2E8F0 50%, #EDF2F7 100%);
      min-height: 100vh; padding: 32px 20px;
    }

    /* Page Header */
    .page-header { text-align: center; margin-bottom: 24px; }
    .page-header h1 { font-size: 22px; font-weight: 700; color: #1A202C; letter-spacing: 1px; }
    .page-header .subtitle { font-size: 13px; color: #718096; margin-top: 6px; }

    /* Left Legend */
    .legend-panel {
      position: fixed; top: 50%; left: 20px;
      transform: translateY(-50%);
      display: flex; flex-direction: column; gap: 10px;
      background: #fff; border-radius: 10px; padding: 14px 16px;
      box-shadow: 0 2px 12px rgba(0,0,0,0.08);
      border: 1px solid #E2E8F0; z-index: 10;
    }
    .legend-panel .legend-title { font-size: 12px; font-weight: 600; color: #64748B; text-align: center; margin-bottom: 4px; }
    .legend-item { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #475569; }
    .legend-dot { width: 18px; height: 8px; border-radius: 4px; }

    /* Right Toolbar */
    .toolbar-panel {
      position: fixed; top: 50%; right: 20px;
      transform: translateY(-50%);
      display: flex; flex-direction: column; gap: 8px;
      background: #fff; border-radius: 10px; padding: 12px;
      box-shadow: 0 2px 12px rgba(0,0,0,0.08);
      border: 1px solid #E2E8F0; z-index: 10;
    }
    .toolbar-panel button {
      padding: 8px 14px; border: 1px solid #E2E8F0; border-radius: 8px;
      background: #fff; color: #475569; font-size: 13px; cursor: pointer;
      transition: all 0.2s; white-space: nowrap; font-family: inherit;
    }
    .toolbar-panel button:hover { background: #F1F5F9; border-color: #94A3B8; color: #334155; }

    /* Tree Structure */
    .tree-wrapper {
      display: flex; justify-content: center;
      overflow-x: auto; padding: 0 80px 40px;
    }
    .tree { position: relative; transition: transform 0.3s ease; transform-origin: top center; }
    .tree ul {
      display: flex; justify-content: center;
      position: relative; list-style: none;
      padding: 0; margin: 0;
    }
    .tree ul ul { padding-top: var(--connector-h); }
    .tree ul ul::before {
      content: ''; position: absolute;
      top: 0; left: 50%; width: 0; height: var(--connector-h);
      border-left: var(--line-width) solid var(--line-color);
    }
    .tree li {
      display: flex; flex-direction: column; align-items: center;
      position: relative; padding: 0 14px;
    }
    .tree ul ul > li { padding-top: var(--connector-h); }
    .tree ul ul > li::before,
    .tree ul ul > li::after {
      content: ''; position: absolute;
      top: 0; width: 50%; height: var(--connector-h);
    }
    .tree ul ul > li::before {
      right: 50%;
      border-right: var(--line-width) solid var(--line-color);
      border-top: var(--line-width) solid var(--line-color);
    }
    .tree ul ul > li::after {
      left: 50%;
      border-left: var(--line-width) solid var(--line-color);
      border-top: var(--line-width) solid var(--line-color);
    }
    .tree ul ul > li:first-child::before { border-top: none; }
    .tree ul ul > li:last-child::after { border-top: none; }
    .tree ul ul > li:only-child::after { border-left: none; border-top: none; }
    .tree ul ul > li:only-child::before { border-top: none; }
    .tree > ul > li { padding-top: 0; }
    .tree > ul > li::before, .tree > ul > li::after { display: none; }

    /* Toggle Button */
    .toggle-btn {
      position: relative; z-index: 4;
      width: 20px; height: 20px; margin-top: 2px;
      border: 2px solid var(--line-color); border-radius: 50%;
      background: #fff; cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      box-shadow: 0 1px 4px rgba(0,0,0,0.1);
      transition: all 0.25s ease; user-select: none;
    }
    .toggle-btn:hover { border-color: #64748B; background: #F8FAFC; box-shadow: 0 2px 8px rgba(0,0,0,0.15); transform: scale(1.15); }
    .toggle-btn::before { content: ''; display: block; width: 10px; height: 2px; background: #64748B; }
    .toggle-btn.collapsed::after { content: ''; position: absolute; width: 2px; height: 10px; background: #94A3B8; }
    li.collapsed > ul { display: none !important; }
    li.collapsed > .toggle-btn { border-color: #CBD5E0; }

    .child-count {
      position: absolute; top: -7px; right: -8px;
      background: #64748B; color: #fff;
      font-size: 9px; font-weight: 700;
      min-width: 14px; height: 14px; border-radius: 7px;
      display: flex; align-items: center; justify-content: center;
      padding: 0 3px;
    }
    .toggle-btn.collapsed .child-count { background: #94A3B8; }

    /* Node Card */
    .node-card {
      position: relative; z-index: 2;
      width: 180px; background: var(--bg-node);
      border-radius: 10px; box-shadow: var(--shadow);
      border: 1px solid #E2E8F0; overflow: hidden;
      transition: transform 0.2s, box-shadow 0.2s; cursor: default;
    }
    .node-card:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(0,0,0,0.12); }
    .node-card.root {
      width: 200px; background: var(--bg-root);
      border: 2px solid var(--c-quanzi);
    }
    .card-header { display: flex; justify-content: center; align-items: center; padding: 10px 12px 8px; }
    .card-header .name {
      font-size: 13px; font-weight: 700; color: #fff;
      padding: 4px 16px; border-radius: 12px;
      text-align: center; letter-spacing: 0.5px;
    }
    .node-card.root .card-header .name { font-size: 15px; padding: 5px 20px; border-radius: 14px; }
    .card-body { padding: 2px 12px 10px; }
    .card-row {
      display: flex; justify-content: space-between; align-items: center;
      padding: 3px 0; font-size: 12px; border-top: 1px solid #F1F5F9;
    }
    .card-row:first-child { border-top: none; }
    .card-row .label { color: #94A3B8; }
    .card-row .value { color: #334155; font-weight: 500; }

    /* Edge Label */
    .edge-label {
      position: absolute; top: 10px; left: 50%;
      transform: translateX(-50%); z-index: 3;
      display: flex; align-items: center; gap: 5px;
      background: #fff; border: 1px solid #E2E8F0;
      border-radius: 12px; padding: 2px 6px 2px 2px;
      white-space: nowrap; box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    }
    .method-tag { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; color: #fff; }
    .ratio-text { font-size: 11px; font-weight: 600; color: #475569; }

    /* Color Helpers */
    .tag-quanzi { background: var(--c-quanzi); }
    .tag-konggu { background: var(--c-konggu); }
    .tag-lianying { background: var(--c-lianying); }

    /* Responsive */
    @media (max-width: 768px) {
      .legend-panel, .toolbar-panel { position: static; transform: none; flex-direction: row; flex-wrap: wrap; justify-content: center; margin: 0 auto 16px; max-width: 600px; }
      .tree-wrapper { padding: 0 16px 40px; }
    }
  </style>
</head>
<body>

<div class="legend-panel">
  <div class="legend-title">出资方式</div>
  <div class="legend-item"><div class="legend-dot" style="background:var(--c-quanzi);"></div><span>全资</span></div>
  <div class="legend-item"><div class="legend-dot" style="background:var(--c-konggu);"></div><span>控股</span></div>
  <div class="legend-item"><div class="legend-dot" style="background:var(--c-lianying);"></div><span>联营</span></div>
</div>

<div class="toolbar-panel">
  <button onclick="expandAll()">全部展开</button>
  <button onclick="collapseAll()">全部折叠</button>
  <button onclick="zoomIn()">放大 +</button>
  <button onclick="zoomOut()">缩小 −</button>
  <button onclick="resetZoom()">重置</button>
</div>

<div class="page-header">
  <h1>产权关系层级树状图</h1>
  <div class="subtitle">点击 +/- 可折叠或展开子节点</div>
</div>

<div class="tree-wrapper">
<div class="tree" id="treeRoot">
  <ul>
    <li id="root-node">
      <!-- 根节点卡片和数据由模型根据用户实际数据填充 -->
      <span class="toggle-btn" onclick="toggleNode(this)"><span class="child-count">2</span></span>
      <ul>
        <li>
          <div class="edge-label"><span class="method-tag tag-quanzi">全资</span><span class="ratio-text">100%</span></div>
          <!-- 子节点卡片 -->
        </li>
        <li>
          <div class="edge-label"><span class="method-tag tag-konggu">控股</span><span class="ratio-text">80%</span></div>
          <!-- 子节点卡片 -->
        </li>
      </ul>
    </li>
  </ul>
</div>
</div>

<script>
let scale = 1;
const treeEl = document.getElementById('treeRoot');
const wrapperEl = document.querySelector('.tree-wrapper');

function toggleNode(btn) {
  const li = btn.parentElement;
  const isCollapsed = li.classList.toggle('collapsed');
  btn.classList.toggle('collapsed', isCollapsed);
}
function expandAll() {
  document.querySelectorAll('.tree li.collapsed').forEach(li => {
    li.classList.remove('collapsed');
    const btn = li.querySelector(':scope > .toggle-btn');
    if (btn) btn.classList.remove('collapsed');
  });
}
function collapseAll() {
  document.querySelectorAll('.tree li').forEach(li => {
    const btn = li.querySelector(':scope > .toggle-btn');
    if (btn && li.id !== 'root-node') { li.classList.add('collapsed'); btn.classList.add('collapsed'); }
  });
}
function zoomIn() { scale = Math.min(scale + 0.1, 2); treeEl.style.transform = `scale(${scale})`; treeEl.style.transformOrigin = 'top center'; }
function zoomOut() { scale = Math.max(scale - 0.1, 0.3); treeEl.style.transform = `scale(${scale})`; treeEl.style.transformOrigin = 'top center'; }
function resetZoom() { scale = 1; treeEl.style.transform = 'scale(1)'; }
function autoFit() {
  const treeWidth = treeEl.scrollWidth;
  const viewWidth = wrapperEl.clientWidth;
  if (treeWidth > viewWidth) { scale = Math.max(0.4, viewWidth / treeWidth); treeEl.style.transform = `scale(${scale})`; treeEl.style.transformOrigin = 'top center'; }
}
window.addEventListener('load', autoFit);
window.addEventListener('resize', autoFit);
</script>
</body>
</html>
```

> **使用说明**：将此代码复制到 `.html` 文件中即可运行。根据实际数据替换注释部分。
