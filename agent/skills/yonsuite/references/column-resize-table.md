# 表格列宽拖拽实现 · column-resize.html

## 核心逻辑

每列表头 `<th>` 内含一个绝对定位的手柄 `<div class="resize-handle">`，监听 mousedown → mousemove → mouseup 全局事件链。

### 结构要求

```html
<table id="mainTable">
  <colgroup id="colGroup"></colgroup>   <!-- JS 动态写入 <col> -->
  <thead id="thead">
    <tr id="headerRow"></tr>            <!-- JS 动态写入 <th> -->
  </thead>
  <tbody></tbody>
</table>
```

`<colgroup>` 和 `<thead>` 必须分开——`table-layout:fixed` 下两者独立，只有同时更新 `<col style="width:NNpx">` 和 `<th style="width:NNpx">` 才能同步。

### 最小列宽设计

每列设置 `data-min-w`，防止拖拽过窄：

```javascript
th.dataset.minW = Math.max(40, label.length * 14 + 24);
```

### 完整 JS 实现

```javascript
// ── 数据驱动构建 ─────────────────────────────────────────────
const COLS = [
  { key: 'code', label: '单据编号', w: 120 },
  // ...
];

const colGroup = document.getElementById('colGroup');
const headerRow = document.getElementById('headerRow');
COLS.forEach((col, i) => {
  // colgroup col
  const c = document.createElement('col');
  c.style.width = col.w + 'px';
  c.dataset.idx = i;
  colGroup.appendChild(c);

  // th
  const th = document.createElement('th');
  th.style.width = col.w + 'px';
  th.dataset.idx = i;
  th.dataset.minW = Math.max(40, col.label.length * 14 + 24);
  th.style.position = 'relative';   // 手柄 absolute 依赖这个

  const lbl = document.createElement('span');
  lbl.textContent = col.label;
  th.appendChild(lbl);

  const handle = document.createElement('div');
  handle.className = 'resize-handle';
  handle.dataset.idx = i;
  th.appendChild(handle);
  headerRow.appendChild(th);
});

// ── 拖拽逻辑 ─────────────────────────────────────────────────
let dragIdx = null;
let dragStartX = 0;
let dragStartW = 0;

document.addEventListener('mousedown', e => {
  const handle = e.target.closest('.resize-handle');
  if (!handle) return;
  e.preventDefault();
  dragIdx = parseInt(handle.dataset.idx);
  dragStartX = e.clientX;
  dragStartW = parseInt(headerRow.children[dragIdx].style.width) || COLS[dragIdx].w;
  handle.classList.add('dragging');
  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';
});

document.addEventListener('mousemove', e => {
  if (dragIdx === null) return;
  const dx = e.clientX - dragStartX;
  const newW = Math.max(
    parseInt(headerRow.children[dragIdx].dataset.minW),
    dragStartW + dx
  );
  const wStr = Math.round(newW) + 'px';
  headerRow.children[dragIdx].style.width = wStr;
  colGroup.children[dragIdx].style.width = wStr;
});

document.addEventListener('mouseup', () => {
  if (dragIdx === null) return;
  headerRow.children[dragIdx].querySelector('.resize-handle')?.classList.remove('dragging');
  dragIdx = null;
  document.body.style.cursor = '';
  document.body.style.userSelect = '';
});
```

### CSS 要点

```css
table { table-layout: fixed; width: 1600px; }  /* 必须 fixed 才能同步列宽 */
thead th { position: sticky; top: 0; overflow: visible; }  /* sticky + visible 保证手柄不截断 */
.resize-handle {
  position: absolute; right: 0; top: 0; bottom: 0;
  width: 6px; cursor: col-resize;
  display: flex; align-items: center; justify-content: center;
}
.resize-handle::after {
  content: ''; width: 2px; height: 18px;
  background: #c0c8ff; border-radius: 1px;
  opacity: 0; transition: opacity 0.15s;
}
.resize-handle:hover::after,
.resize-handle.dragging::after { opacity: 1; background: #4a60e0; }
```

### 已知坑

- **不能用 `mouseleave` 代替全局 `mouseup`**：用户鼠标甩出表格区域时拖拽应该终止
- **`table-layout:fixed` + `overflow-x:auto` 组合**：colgroup 列宽在 Chrome/Firefox/Safari 均生效；不用 `style="width"` 而是用 `<col style="width">`
- **`sticky` 与 `overflow` 冲突**：手柄放在 `th` 内部（`overflow:visible` 继承）而非外部包装，`position:sticky` 失效但手柄可点击；实测两者均可工作
