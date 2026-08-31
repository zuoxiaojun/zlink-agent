# 布局基础配置（必读）

> 布局规则，所有图表必须加载。

---

## 一、标题配置

### 通用配置

| 属性 | 值 |
| ------ | ----- |
| left | 16 |
| top | 8 |
| textStyle.fontSize | 14 |
| textStyle.fontWeight | 600 |
| textStyle.color | #374151 |

### 模板代码

```javascript
const titleTemplate = {
  left: 16,
  top: 8,
  textStyle: {
    fontSize: 14,
    fontWeight: 600,
    color: '#374151'
  }
};
```

### 重要约束

**使用 option.title 设置标题，禁止在图表上方单独添加标题元素**

---

## 二、图例配置

### 通用配置（所有图表）

| 属性 | 值 |
| ------ | ----- |
| show | true |
| bottom | 8 |
| left | center |
| itemWidth | 12 |
| itemHeight | 12 |
| itemGap | 16 |

### 模板代码

```javascript
const legendTemplate = {
  show: true,  // 强制显示，单系列也需要
  bottom: 8,
  left: 'center',
  itemWidth: 12,
  itemHeight: 12,
  itemGap: 16
};
```

### 注意事项

- 所有图表必须有图例，单系列也不例外
- **必须设置 `show: true`**，否则单系列图表图例不显示
- 图例位置统一在图表正下方

---

## 三、Grid 布局配置

### containLabel 四维行为解析（必读）

`containLabel: true` 是 ECharts 的标签溢出自动处理机制。但它的作用范围**不是四向全通**的：

| 方向 | containLabel 是否生效？ | 取决于 | 应对方案 |
| ------ | ------------------------ | -------- | --------- |
| **Left** | ✅ **生效** | `yAxis: { type: 'category' }` 时(横向条图) | 给最小值 left:70，containLabel 自动扩张 |
| **Bottom** | ✅ **生效** | `xAxis: { type: 'category' }` 时(垂直柱图) | 给最小值 bottom:60，containLabel 自动扩张 |
| **Top** | ❌ **不生效** | containLabel 不处理标题/工具区域 | 由 calcAdaptiveGrid 精确计算 top=50 |
| **Right** | ❌ **不生效于 data label** | containLabel 只处理轴标签，不处理 series 的数值标签 | 由 calcAdaptiveGrid 根据数据内容计算 |

**核心原则**：`containLabel` 配合小 left 值（如 70），会自动根据轴标签内容扩张到精确宽度。
**禁止**：手动加大 left 值（如 left:200），会导致 containLabel 计算失真、绘图区被过度压缩。

---

### 四维自适应策略（三层次安全防御）

| 层次 | 机制 | 覆盖方向 | 说明 |
| ------ | ------ | --------- | ------ |
| Layer 1 | `containLabel: true`（ECharts 原生） | Left, Bottom | 零代码，轴标签自动扩展 |
| Layer 2 | `calcAdaptiveGrid()`（数据驱动的预计算函数） | Top, Right | 精确计算，不依赖 DOM |
| Layer 3 | 钳位：min=70, max=160 | 所有方向 | 极端值保护，防止布局崩塌 |

**模板代码见 `templates/echarts/common.js` → `calcAdaptiveGrid` 函数**。

---

### 默认配置

| 场景 | top | right | bottom | left | 自适应策略 |
| ------ | ----- | ------- | -------- | ------ | ---------- |
| 默认（垂直柱图/折线） | 50 | 70 | 60 | 70 | 由模板函数自动调用 calcAdaptiveGrid |
| 横向条图/排名图 | 50 | 自动计算(70-160) | 60 | 70 | 使用 `createHorizontalCartesianOption` |
| 有 markLine | 50 | 90 | 60 | 70 | calcAdaptiveGrid + manual right override |
| 有 dataZoom | 50 | 70 | 80 | 70 | calcAdaptiveGrid + manual bottom override |

---

### dataZoom 与 legend 共存布局（强制）

当 dataZoom slider 与 legend 同时存在时，必须按以下垂直堆叠顺序定位，**禁止两者使用相同 bottom 值**（会导致视觉重叠）：

| 层级（自下往上） | 组件 | bottom 值 | 说明 |
| ---------------- | ------ | ---------- | ------ |
| 1（最底） | dataZoom.slider | 8 | 贴底 |
| 2 | legend | 38 | = slider.bottom(8) + slider.height(22) + gap(8) |
| 3 | grid 绘图区 | 80 | = legend.bottom(38) + legend 高度(约 30) + 缓冲(12) |

**计算公式**：

- `legend.bottom = dataZoom.bottom + dataZoom.height + 8`
- `grid.bottom = legend.bottom + 30`

**关键约束**：

- dataZoom.slider 的 `bottom` 固定 8，`height` 固定 22
- legend 的 `bottom` 必须按公式计算，禁止与 dataZoom 相同
- grid.bottom 必须 ≥ 80，给 legend + slider 留够空间

**标准配方**（直接引用，禁止手写 bottom 值）：

- `dataZoomWithLegend`（见 [templates/echarts/common.js](../../templates/echarts/common.js)）
- `legendWithZoom`（见 [templates/echarts/common.js](../../templates/echarts/common.js)）

### 响应式 grid

| 屏幕宽度 | top | right | bottom | left |
| --------- | ----- | ------- | -------- | ------ |
| < 500px | 40 | sidebar auto | 50 | sidebar auto |
| 500-700px | 45 | sidebar auto | 55 | sidebar auto |
| > 700px | 50 | sidebar auto | 60 | sidebar auto |

> 响应式场景下 left/right 仍由 containLabel 或 calcAdaptiveGrid 自动处理。

### 模板代码

```javascript
const gridTemplate = {
  top: 60,
  right: 70,
  left: 70,
  bottom: 60,
  containLabel: true
};


function getResponsiveGrid(containerWidth) {
  if (containerWidth < 500) {
    return { top: 50, right: 50, left: 50, bottom: 50 };
  } else if (containerWidth < 700) {
    return { top: 55, right: 60, left: 60, bottom: 55 };
  }
  return { top: 60, right: 70, left: 70, bottom: 60 };
}
```

---

## 四、容器配置

### 尺寸配置

| 属性 | 值 |
| ------ | ----- |
| height | 400px |
| max_width_single | 900px |
| mobile_height | 320px |

### HTML 结构

```html
<div id="chart1" class="chart-container">
  <div class="loading-placeholder">图表渲染中...</div>
</div>
```

**必须内嵌 loading 占位符，禁止生成空容器**

### CSS 样式

```css
.chart-container {
  width: 100%;
  height: 400px;
}

.loading-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #8c8c8c;
  font-size: 14px;
  background: #fafafa;
  border-radius: 12px;
  animation: loading-pulse 1.5s ease-in-out infinite;
}

@keyframes loading-pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}

@media (max-width: 768px) {
  .chart-container { height: 320px; }
}
```

---

## 五、坐标轴配置

### Y轴名称样式

| 属性 | 值 | 说明 |
| ------ | ----- | ------ |
| nameTextStyle.fontSize | 12 | 固定 |
| nameTextStyle.color | 见下方规则 | 按轴对应的系列数判断 |

### Y轴名称配色规则

> 仅当 yAxis 设了 `name` 时适用；无 name 时本规则不生效（无需设 nameTextStyle.color）。

| 场景 | Y轴名称颜色 |
| ------ | ------------ |
| 该轴对应 1 个系列 | 与该系列色一致 |
| 该轴对应多个系列 | 降级默认 `#666666` |

**色值对应规则**：Y轴名称颜色 = 该轴对应系列的系列色

- 单系列（1 轴 1 系列）→ 系列色 `#3293fb` → 轴名称 `#3293fb`
- 双轴图（左轴 1 系列、右轴 1 系列）→ 左系列色 `#3293fb` → 左轴名称 `#3293fb`；右系列色 `#fcb530` → 右轴名称 `#fcb530`
- 多系列单轴（1 轴 3 系列）→ 无法对应 → 降级 `#666666`

### 模板代码

```javascript
// 单系列：Y轴名称与图例同色
yAxis: [{
  type: 'value',
  name: '实际收入(万元)',
  nameTextStyle: { color: '#3293fb', fontSize: 12 },
  axisLabel: { ... }
}]

// 双轴图：每轴与对应系列同色
yAxis: [
  { type: 'value', name: '实际收入(万元)', nameTextStyle: { color: '#3293fb', fontSize: 12 }, axisLabel: { ... } },
  { type: 'value', name: '销售数量(件)',   nameTextStyle: { color: '#fcb530', fontSize: 12 }, axisLabel: { ... } }
]

// 多系列单轴：降级默认灰色
yAxis: [{
  type: 'value',
  name: '实际收入(万元)',
  nameTextStyle: { color: '#666666', fontSize: 12 },
  axisLabel: { ... }
}]
```

---

## 六、Toolbox 配置

### 配置规则

| 图表类型 | 配置 | 说明 |
| --------- | ------ | ------ |
| 直角坐标系（bar/line/area） | `cartesianToolbox` | 包含 saveAsImage + magicType + restore |
| 非直角坐标系（pie/radar/scatter 等） | `baseToolbox` | 仅包含 saveAsImage |

### 直角坐标系 Toolbox

```javascript
const cartesianToolbox = {
  show: true,
  right: 10,
  top: 0,
  itemSize: 15,
  itemGap: 10,
  feature: {
    saveAsImage: { title: '保存为图片', pixelRatio: 2 },
    magicType: { type: ['line', 'bar'], title: { line: '折线图', bar: '柱状图' } },
    restore: { title: '还原' }
  }
};
```

### 非直角坐标系 Toolbox

```javascript
const baseToolbox = {
  show: true,
  right: 10,
  top: 0,
  itemSize: 15,
  itemGap: 10,
  feature: {
    saveAsImage: { title: '保存为图片', pixelRatio: 2 }
  }
};
```

### 模板引用

- 直角坐标系：`templates/echarts/option_cartesian.js` → 使用 `cartesianToolbox`
- 非直角坐标系：`templates/echarts/option_non_cartesian.js` → 使用 `baseToolbox`

---

## 七、常见错误对照表

**禁止自行编写配置值。所有配置必须从本文件复制。**

| 配置项 | 常见错误 | 正确值 |
| -------- | --------- | -------- |
| title.left | ❌ `'center'` | ✅ `16` |
| title.textStyle.fontSize | ❌ `16` | ✅ `14` |
| legend.bottom | ❌ 使用 `top` | ✅ `bottom: 8` |
| legend.itemWidth | ❌ 未设置 | ✅ `12` |
| legend.itemHeight | ❌ 未设置 | ✅ `12` |
| grid.top（无yAxis.name） | ❌ 自定义值 | ✅ `60` 或调用 calcAdaptiveGrid |
| grid.top（有yAxis.name） | ❌ `50` 或 `60` | ✅ `80` 或调用 calcAdaptiveGrid |
| grid.left | ❌ 手动加大（如 `200`） | ✅ `70` + containLabel 自动扩张 |
| grid.containLabel | ❌ 未设置 | ✅ `true` |
| legend.bottom（有 dataZoom） | ❌ 与 dataZoom 相同（如都设 8） | ✅ `38`（= dataZoom.bottom 8 + height 22 + gap 8） |
