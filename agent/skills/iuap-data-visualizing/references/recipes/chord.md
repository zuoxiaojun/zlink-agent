# 和弦图（Chord / Chord Diagram）

> 展示节点间的双向关系和权重

> **注意**：ECharts 5 已移除内置 chord 类型，需要用 `custom` 或 `graph` + circular 布局替代。

### 使用 graph + circular 布局替代

```javascript
series: [{
  type: 'graph',
  layout: 'circular',
  circular: { rotateLabel: true },
  data: [
    { name: 'A', symbolSize: 60 },
    { name: 'B', symbolSize: 50 },
    { name: 'C', symbolSize: 45 },
    { name: 'D', symbolSize: 40 }
  ],
  links: [
    { source: 'A', target: 'B', value: 30, lineStyle: { width: 3 } },
    { source: 'A', target: 'C', value: 20, lineStyle: { width: 2 } },
    { source: 'B', target: 'C', value: 15, lineStyle: { width: 1.5 } },
    { source: 'B', target: 'D', value: 25, lineStyle: { width: 2.5 } },
    { source: 'C', target: 'D', value: 10, lineStyle: { width: 1 } }
  ],
  label: { fontSize: 12, color: '#374151' },
  edgeSymbol: ['none', 'arrow'],
  edgeSymbolSize: 6,
  lineStyle: { opacity: 0.6, curveness: 0.3 },
  emphasis: { focus: 'adjacency' },
  roam: true
}],
labelLayout: { hideOverlap: true }
```
