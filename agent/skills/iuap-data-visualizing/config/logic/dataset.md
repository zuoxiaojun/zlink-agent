# dataset 模式规则（必读）

> **适用范围**：L1/L2 图表（柱/线/饼/雷达/散点/双轴）必须使用 dataset 模式。L3 特殊图表（custom/tree/sankey/wordcloud/liquidfill 等）按图表类型原生数据模式（series.data），不强制 dataset。层级定义见 [SKILL.md → 实现层级](../SKILL.md#实现层级按图表类型选择)。

---

## 完整示例（直接复制）

```javascript
// ========== 公共函数（必须内联）==========

function safeGetValue(params) {
  if (Array.isArray(params.value)) {
    return params.value[params.seriesIndex + 1];
  }
  return params.value;
}

function formatUnified(value, forAxis) {
  if (value == null || typeof value !== 'number' || isNaN(value)) return '--';
  var decimals = forAxis ? 1 : 2;
  if (value >= 100000000) {
    return (value / 100000000).toFixed(decimals) + '亿';
  } else if (value >= 10000) {
    return (value / 10000).toFixed(decimals) + '万';
  }
  return forAxis ? value.toLocaleString() : value.toFixed(2);
}

function formatTooltipAxis(params) {
  if (!params || params.length === 0) return '';
  var category = params[0].value[0];  // 第0列是类目
  var lines = params.map(function(p) {
    var v = safeGetValue(p);
    return p.seriesName + ': ' + formatUnified(v, false);
  });
  return category + '<br/>' + lines.join('<br/>');
}

// ========== 数据集 ==========

const datasetSource = [
  ['地区', '实际收入', '销售数量'],
  ['华东区', 4620065, 3114],
  ['华北区', 2921996, 1877],
  ['西南区', 2495316, 1679]
];

// ========== 图表配置 ==========

const option = {
  title: {
    left: 16,
    top: 8,
    text: '各大区实际收入与销售数量',
    textStyle: { fontSize: 14, fontWeight: 600, color: '#374151' }
  },
  tooltip: {
    trigger: 'axis',
    formatter: formatTooltipAxis
  },
  legend: {
    bottom: 8,
    left: 'center',
    itemWidth: 12,
    itemHeight: 12
  },
  dataset: { source: datasetSource },
  grid: { top: 60, right: 70, left: 70, bottom: 60, containLabel: true },
  xAxis: { type: 'category' },
  yAxis: [
    {
      type: 'value',
      name: '实际收入(万元)',
      nameTextStyle: { color: '#666666', fontSize: 12 },
      axisLabel: { formatter: function(v) { return formatUnified(v, true); } }
    },
    {
      type: 'value',
      name: '销售数量(件)',
      nameTextStyle: { color: '#666666', fontSize: 12 },
      axisLabel: { formatter: function(v) { return v.toLocaleString(); } }
    }
  ],
  series: [
    { type: 'bar', yAxisIndex: 0 },
    { type: 'bar', yAxisIndex: 1 }
  ]
};
```

---

## 关键约束

| 约束 | 说明 |
| ------ | ------ |
| 类目取值 | `params[0].value[0]`，禁止使用 `params.name` |
| 数值取值 | `safeGetValue(params)`，禁止直接使用 `params.value` |
| series 配置 | bare series（只声明 type）走主题色板；如需语义化用色，用 `generate*Series` 显式传色。禁止手写 itemStyle.color 但不同步 lineStyle.color |
| 公共函数 | 必须内联到 HTML 中 |

---

## 三维数据场景

当数据包含**两个分类维度**（如"大区+业务员"）和一个数值指标时，需要使用堆叠柱图。

**详细规则** → [dataset-stacked.md](dataset-stacked.md)
