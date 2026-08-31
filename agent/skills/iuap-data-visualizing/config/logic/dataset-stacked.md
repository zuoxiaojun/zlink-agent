# 三维数据堆叠柱图规则

> 当数据包含两个分类维度（如"大区+业务员"）和一个数值指标时使用本规则。

---

## 数据格式对比

| 格式 | 结构 | 示例 |
|------|------|------|
| 长格式 | 维度1、维度2、数值 | `['华东', '李芳', 69877]` |
| 宽格式 | 维度2、维度1值1、维度1值2... | `['李芳', 69877, 0, 45367]` |

---

## 转换原则

**铁律**：第一个分类维度作为**系列**，第二个分类维度作为**类目**

| 原始数据 | 转换后 |
|----------|--------|
| 大区（维度1）、业务员（维度2）、销售金额 | 业务员为类目，大区为系列 |

---

## 完整示例（直接复制）

```javascript
// 长格式原始数据：大区、业务员、销售金额
// 转换为宽格式：业务员为类目，大区为系列

const datasetSource = [
  ['业务员', '华东', '华中', '华北', '西北', '西南'],
  ['李芳', 69877, 0, 0, 45367, 0],
  ['张颖', 60635, 52720, 58820, 0, 55116],
  ['孙林', 57534, 0, 56347, 0, 0],
  ['郑建杰', 55840, 62249, 82550, 0, 0]
];

const option = {
  title: {
    left: 16,
    top: 8,
    text: '各区域业务员销售贡献',
    textStyle: { fontSize: 14, fontWeight: 600, color: '#374151' }
  },
  tooltip: {
    trigger: 'axis',
    formatter: function(params) {
      if (!params || params.length === 0) return '';
      var category = params[0].value[0];
      var lines = params.map(function(p) {
        var v = p.value[p.seriesIndex + 1];
        if (v === 0) return null;  // 跳过0值
        return p.seriesName + ': ' + (v/10000).toFixed(2) + '万';
      }).filter(Boolean);
      return category + '<br/>' + lines.join('<br/>');
    }
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
  yAxis: {
    type: 'value',
    name: '销售金额(万元)',
    nameTextStyle: { color: '#666666', fontSize: 12 },
    axisLabel: { formatter: function(v) { return (v/10000).toFixed(0) + '万'; } }
  },
  series: [
    { type: 'bar', name: '华东', stack: 'total', itemStyle: { barBorderRadius: [3, 3, 0, 0] } },
    { type: 'bar', name: '华中', stack: 'total' },
    { type: 'bar', name: '华北', stack: 'total' },
    { type: 'bar', name: '西北', stack: 'total' },
    { type: 'bar', name: '西南', stack: 'total' }
  ]
};
```

---

## 关键配置说明

| 配置项 | 说明 |
| -------- | ------ |
| `stack: 'total'` | 所有系列使用相同 stack 值，实现堆叠效果 |
| `series[0].itemStyle` | 仅第一个系列配置圆角，避免堆叠时圆角错位 |
| `tooltip formatter` | 过滤0值，避免显示无意义的系列 |

---

## 常见错误

```javascript
// ❌ 错误：直接使用长格式，图表无法正确渲染
dataset: { source: [['大区', '业务员', '销售金额'], ['华东', '李芳', 69877], ...] }
series: [{ type: 'bar' }]  // 单系列无法处理三维数据

// ✅ 正确：转换为宽格式，使用堆叠柱图
dataset: { source: [['业务员', '华东', '华中', ...], ['李芳', 69877, 0, ...], ...] }
series: [{ type: 'bar', stack: 'total' }, { type: 'bar', stack: 'total' }, ...]
```
