# ECharts 进阶能力参考

本文件包含 ECharts 图表的高级配置，按需查阅。

---

## 1. 渲染器选择（Canvas vs SVG）

```javascript
// Canvas 渲染器（默认，适合大数据量）
echarts.init(dom, null, { renderer: 'canvas' });

// SVG 渲染器（适合移动端、少量数据、需要高清缩放）
echarts.init(dom, null, { renderer: 'svg' });
```

| 场景 | 推荐渲染器 | 原因 |
| ------ | ----------- | ------ |
| 数据量 > 1000 | Canvas | 大数据渲染性能更好 |
| 移动端 / 低端设备 | SVG | 内存占用更低 |
| 需要高清缩放 / 打印 | SVG | 矢量不模糊 |
| 多图表实例（>10个） | SVG | 减少 Canvas 内存压力 |
| 涟漪效果 / 热力图混合 | Canvas | 部分特效仅支持 Canvas |

**注意**：CDN 全量引入 `echarts.min.js` 时两种渲染器均已内置，无需额外导入。

---

## 2. 大数据性能优化

### 触发规则

```
数据量 ≤ 1000    → 默认配置即可
数据量 1000-3000 → 启用 large: true
数据量 > 3000    → 启用 large + progressive 增量渲染
```

### 配置示例

```javascript
// 大数据折线图/散点图（使用 dataset 统一管理数据）
dataset: {
  source: largeDataArray
},
series: [{
  type: 'scatter',
  large: true,
  largeThreshold: 2000
}]

// 增量渲染（适用于柱状图等）
series: [{
  type: 'bar',
  progressive: 200,
  progressiveThreshold: 3000
}]
```

### 折线图降采样

```javascript
series: [{
  type: 'line',
  sampling: 'lttb'    // Largest-Triangle-Three-Buckets，可安全处理 10 万+ 数据点
}]
```

### 关闭动画

大数据量时建议关闭入场动画：

```javascript
animation: false
// 或缩短动画时间
animationDuration: 300
```

---

## 3. 图表标注系统

### markLine — 标线（平均线、目标线、警戒线）

```javascript
series: [{
  type: 'bar',
  markLine: {
    symbol: ['none', 'none'],
    data: [
      { type: 'average', name: '平均值' },
      { yAxis: 180, name: '目标线', lineStyle: { color: '#ff4d4f', type: 'dashed' } },
      [
        { coord: [0, 150], name: '起点' },
        { coord: [6, 180], name: '终点' }
      ]
    ],
    lineStyle: { width: 1.5, type: 'dashed' },
    label: { position: 'insideEndTop', formatter: '{b}: {c}' }
  }
}]
```

### markPoint — 标注点（最大值、最小值）

```javascript
series: [{
  type: 'line',
  markPoint: {
    data: [
      { type: 'max', name: '最大值' },
      { type: 'min', name: '最小值' }
    ],
    symbolSize: 50,
    label: { fontSize: 12 }
  }
}]
```

### markArea — 标注区域

```javascript
series: [{
  type: 'line',
  markArea: {
    silent: true,
    data: [
      [{ name: '目标区间', xAxis: '周一', itemStyle: { color: 'rgba(50,147,251,0.1)' } },
       { xAxis: '周三' }],
      [{ name: '警戒区', xAxis: '周五', itemStyle: { color: 'rgba(255,77,79,0.1)' } },
       { xAxis: '周六' }]
    ]
  }
}]
```

### 何时使用标注

| 用户意图 | 标注类型 |
| --------- | --------- |
| "标出平均线" / "平均值" | markLine + type: 'average' |
| "目标值" / "KPI 线" | markLine + yAxis 固定值 |
| "最高/最低" / "极值" | markPoint + type: 'max'/'min' |
| "关注区域" / "正常范围" | markArea 坐标区间 |
| "同比环比" / 对比参考 | markLine 虚线 + 不同颜色 |

---

## 4. dataZoom 详细配置

> **位置规则**：dataZoom 与 legend 共存时的垂直堆叠顺序与 bottom 值公式见 [config/layout/base.md → dataZoom 与 legend 共存布局](../config/layout/base.md#datazoom-与-legend-共存布局)。此处仅展示写法示例。共存时直接引用 `dataZoomWithLegend` 和 `legendWithZoom` 常量（见 [templates/echarts/common.js](../templates/echarts/common.js)），禁止手写 bottom 值。

```javascript
// 滑动条型缩放（图表底部）
dataZoom: [{
  type: 'slider',
  start: 0, end: 100,
  height: 20, bottom: 10
}]

// 内置型缩放（鼠标滚轮/触摸缩放）
dataZoom: [{
  type: 'inside',
  start: 0, end: 100
}]

// 两者组合（推荐）
dataZoom: [
  { type: 'slider', start: 0, end: 100 },
  { type: 'inside', start: 0, end: 100 }
]
```

### tooltip 富文本格式化

```javascript
tooltip: {
  trigger: 'axis',
  backgroundColor: 'rgba(255,255,255,0.96)',
  borderColor: '#e5e7eb',
  borderWidth: 1,
  textStyle: { color: '#333', fontSize: 13 },
  formatter: function(params) {
    let html = `<div style="font-weight:600;margin-bottom:4px">${params[0].axisValue}</div>`;
    params.forEach(p => {
      html += `<div style="display:flex;align-items:center;gap:6px;margin:2px 0">
        <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color}"></span>
        <span style="flex:1">${p.seriesName}</span>
        <span style="font-weight:600">${typeof p.value === 'number' ? p.value.toLocaleString() : p.value}</span>
      </div>`;
    });
    return html;
  }
}
```

---

## 5. 无障碍访问（ARIA）

### 启用方式

```javascript
option = {
  aria: {
    show: true,
    description: '这是一个关于月度销售额的柱状图',
    decal: {
      show: true    // 贴花图案，色盲用户可通过图案区分数据
    }
  }
};
```

### 自定义 ARIA 描述模板

```javascript
aria: {
  show: true,
  general: {
    withTitle: '这是一个关于"{title}"的图表。',
    withoutTitle: '这是一个图表。'
  },
  series: {
    prefix: '图表类型为{seriesType}，名称为{seriesName}。数据如下：',
    withName: '{seriesName}中{name}的数据为{value}',
    withoutName: '第{seriesIndex}系列中{name}的数据为{value}'
  }
}
```

---

## 6. 组合图（双轴）

```javascript
dataset: {
  source: [
    ['月份', '销售数量', '增长率'],
    ['1月', 320, 5],
    ['2月', 450, 12.5],
    ['3月', 380, -5.2],
    ['4月', 420, 10.9]
  ]
},
yAxis: [
  { type: 'value', name: '数量' },
  { type: 'value', name: '增长率', position: 'right', axisLabel: { formatter: '{value}%' } }
],
series: [
  { name: '销售数量', type: 'bar', yAxisIndex: 0 },
  { name: '增长率', type: 'line', yAxisIndex: 1, smooth: true }
]
```

---

## 7. 动态时间轴

```javascript
timeline: {
  axisType: 'category',
  data: ['2021', '2022', '2023', '2024'],
  autoPlay: true,
  playInterval: 2000,
  label: { formatter: '{value}年' }
},
options: [
  { dataset: { source: [['类别', '值'], ['A', 120], ['B', 200]] }, series: [{ type: 'bar' }] },
  { dataset: { source: [['类别', '值'], ['A', 180], ['B', 250]] }, series: [{ type: 'bar' }] },
  { dataset: { source: [['类别', '值'], ['A', 220], ['B', 280]] }, series: [{ type: 'bar' }] },
  { dataset: { source: [['类别', '值'], ['A', 260], ['B', 310]] }, series: [{ type: 'bar' }] }
]
```

---

## 8. 多图联动

```javascript
dataset: {
  source: [
    ['月份', '销售额', '利润'],
    ['1月', 120, 60], ['2月', 200, 100], ['3月', 150, 80],
    ['4月', 80, 40], ['5月', 70, 30], ['6月', 110, 55]
  ]
},
axisPointer: {
  link: [{ xAxisIndex: 'all' }]
},
grid: [
  { left: '8%', right: '8%', height: '35%' },
  { left: '8%', right: '8%', top: '55%', height: '35%' }
],
xAxis: [
  { gridIndex: 0, type: 'category' },
  { gridIndex: 1, type: 'category' }
],
yAxis: [
  { gridIndex: 0 },
  { gridIndex: 1 }
],
series: [
  { type: 'bar', xAxisIndex: 0, yAxisIndex: 0 },
  { type: 'line', xAxisIndex: 1, yAxisIndex: 1 }
]
```

---

## 9. 自定义图形（custom 渲染器）

```javascript
series: [{
  type: 'custom',
  renderItem: function(params, api) {
    const categoryIndex = api.value(0);
    const start = api.coord([api.value(1), categoryIndex]);
    const end = api.coord([api.value(2), categoryIndex]);
    const height = api.size([0, 1])[1] * 0.6;
    return {
      type: 'rect',
      shape: { x: start[0], y: start[1] - height / 2, width: end[0] - start[0], height: height },
      style: api.style()
    };
  },
  data: [...]
}]
```

---

## 10. 错误恢复机制

### CDN 容灾

```html
<script src="https://registry.npmmirror.com/echarts/5.5.1/files/dist/echarts.min.js"
        onerror="this.onerror=null;this.src='https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js'"></script>
```

### 多级回退

```javascript
const cdnList = [
  'https://registry.npmmirror.com/echarts/5.5.1/files/dist/echarts.min.js',
  'https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js',
  'https://cdn.bootcdn.net/ajax/libs/echarts/5.5.1/echarts.min.js'
];

function loadScript(index) {
  if (index >= cdnList.length) {
    document.getElementById('chart').innerHTML =
      '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#8c8c8c;font-size:14px;">图表库加载失败，请检查网络连接后刷新页面</div>';
    return;
  }
  const s = document.createElement('script');
  s.src = cdnList[index];
  s.onerror = () => loadScript(index + 1);
  s.onload = () => initChart();
  document.head.appendChild(s);
}
loadScript(0);
```

### 地图数据回退

```javascript
async function loadMap() {
  try {
    const resp = await fetch('https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json');
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const geoJson = await resp.json();
    echarts.registerMap('china', geoJson);
    return true;
  } catch (e) {
    console.warn('地图数据加载失败，回退为非地图图表');
    return false;
  }
}
```

### 插件未加载回退

```javascript
if (echarts.seriesTypes && echarts.seriesTypes.wordCloud) {
  series = [{ type: 'wordCloud', data: wordData }];
} else {
  series = [{ type: 'bar', data: wordData.slice(0, 20) }];
}
```

---

## 11. 交互增强

### 框选（brush）

```javascript
brush: {
  toolbox: ['rect', 'polygon', 'lineX', 'lineY', 'keep', 'clear'],
  xAxisIndex: 0,
  brushStyle: {
    borderWidth: 1,
    color: 'rgba(50,147,251,0.15)',
    borderColor: '#3293fb'
  }
}
```

### 数据下钻

```javascript
chart.on('click', function(params) {
  if (params.componentType === 'series') {
    const subData = getSubCategoryData(params.name);
    chart.setOption({
      title: { text: params.name + ' - 明细数据' },
      dataset: { source: subData },
      series: [{ type: 'bar' }]
    }, true);
  }
});
```

### 联动高亮

```javascript
chartA.on('mouseover', function(params) {
  chartB.dispatchAction({ type: 'highlight', seriesIndex: 0, dataIndex: params.dataIndex });
  chartB.dispatchAction({ type: 'showTip', seriesIndex: 0, dataIndex: params.dataIndex });
});
chartA.on('mouseout', function() {
  chartB.dispatchAction({ type: 'downplay' });
  chartB.dispatchAction({ type: 'hideTip' });
});
```

---

## 12. 打印优化

```css
@media print {
  body { background: #fff !important; padding: 0 !important; -webkit-print-color-adjust: exact; }
  #chart { box-shadow: none !important; border: 1px solid #e5e7eb; page-break-inside: avoid; }
  .chart-toolbar { display: none !important; }
}
```

### 演示模式

```javascript
// 用户提到"演示"、"PPT"、"汇报"时
option.title.textStyle.fontSize = 18;
option.series.forEach(s => {
  if (s.label) { s.label.fontSize = 14; s.label.fontWeight = 600; }
  if (s.markLine && s.markLine.label) { s.markLine.label.fontSize = 13; }
});
```

---

## 13. 响应式设计

### ECharts 媒体查询

```javascript
const baseOption = { /* 基础配置 */ };
const media = [
  {
    query: { maxWidth: 600 },
    option: {
      title: { textStyle: { fontSize: 12 } },
      legend: { orient: 'horizontal', top: 0 },
      grid: { top: 60, left: 40, right: 20, bottom: 36 },
      xAxis: { axisLabel: { fontSize: 10, rotate: 30 } },
      yAxis: { axisLabel: { fontSize: 10 } }
    }
  }
];
chart.setOption({ baseOption, media });
```

### 移动端适配要点

| 适配项 | 配置 |
| ------- | ------ |
| 字号缩小 | 标题 12-14px，标签 10-11px |
| 图例位置 | 水平排列，放在顶部或底部 |
| 触摸缩放 | `dataZoom: [{ type: 'inside' }]` |
| SVG 渲染 | `echarts.init(dom, null, { renderer: 'svg' })` |
