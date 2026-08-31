# 直方图（Histogram）

> 展示连续数据的频率分布

**实现方式**：ECharts `bar` + 预计算分箱（bin）。

### 分箱计算

```javascript
function computeHistogram(data, binCount) {
  const min = Math.min(...data);
  const max = Math.max(...data);
  const binWidth = (max - min) / binCount;
  const bins = [];

  for (let i = 0; i < binCount; i++) {
    const lo = min + i * binWidth;
    const hi = lo + binWidth;
    const count = data.filter(v => v >= lo && (i === binCount - 1 ? v <= hi : v < hi)).length;
    bins.push({
      label: `${lo.toFixed(1)}-${hi.toFixed(1)}`,
      range: `[${lo.toFixed(1)}, ${hi.toFixed(1)})`,
      count
    });
  }
  return bins;
}

// Sturges 公式自动计算分箱数
function sturgesBinCount(n) {
  return Math.ceil(1 + Math.log2(n));
}
```

### 配置

```javascript
const bins = computeHistogram(rawData, sturgesBinCount(rawData.length));

dataset: {
  source: bins.map(b => ({ label: b.label, count: b.count }))
},
xAxis: {
  type: 'category',
  axisLabel: { rotate: 30, fontSize: 11 },
  name: '数值区间'
},
yAxis: { type: 'value', name: '频次' },
series: [{
  type: 'bar',
  encode: { x: 'label', y: 'count' },
  barMaxWidth: 60,
  itemStyle: { borderRadius: [2, 2, 0, 0], color: '#3293fb' },
  // 无间距，直方图柱子间无间隔
  barGap: '0%',
  barCategoryGap: '0%'
}],
labelLayout: { hideOverlap: true }
```
