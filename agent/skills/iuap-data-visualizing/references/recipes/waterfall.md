# 瀑布图（Waterfall）

> 展示增量变化过程（如利润构成：收入 → 扣减各项成本 → 净利润）

**实现原理**：两个 `bar` series 叠加——底层透明柱（占位）+ 顶层实际增量柱。使用 dataset 管理预计算后的数据。

```javascript
// 原始数据
const categories = ['1月', '2月', '3月', '4月', '5月'];
const values = [120, -15, 28, -8, 35];  // 正值=增，负值=减

// 计算瀑布图数据
let cumulative = 0;
const bases = [];   // 透明底层高度
const deltas = [];  // 实际增量高度
const totals = [];  // 累计值（用于标签）

values.forEach((v, i) => {
  if (v >= 0) {
    bases.push(cumulative);
    deltas.push(v);
  } else {
    bases.push(cumulative + v);
    deltas.push(-v);
  }
  cumulative += v;
  totals.push(cumulative);
});

// 将预计算结果组装为 dataset
dataset: {
  source: categories.map((cat, i) => ({
    category: cat,
    base: bases[i],
    delta: deltas[i],
    originalValue: values[i]
  }))
},
series: [
  {
    name: '占位',
    type: 'bar',
    stack: 'waterfall',
    encode: { x: 'category', y: 'base' },
    itemStyle: { color: 'transparent' },
    barMaxWidth: 40,
    tooltip: { show: false }
  },
  {
    name: '变化',
    type: 'bar',
    stack: 'waterfall',
    encode: { x: 'category', y: 'delta' },
    itemStyle: {
      color: function(params) {
        return params.data.originalValue >= 0 ? '#3293fb' : '#ff4d4f';
      }
    },
    label: {
      show: true,
      position: 'top',
      formatter: function(params) {
        const val = params.data.originalValue;
        return (val >= 0 ? '+' : '') + val;
      },
      fontSize: 11
    },
    barMaxWidth: 40
  }
],
labelLayout: { hideOverlap: true }
```

### 首尾合计柱

```javascript
// 在 dataset source 开头添加"总计"行（从 0 到最终累计值）
categories.unshift('总计');
bases.unshift(0);
deltas.unshift(cumulative);
// 总计柱用不同颜色标记（在 itemStyle.color 函数中判断 dataIndex === 0）
```
