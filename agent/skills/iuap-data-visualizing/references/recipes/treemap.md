# 矩形树图（Treemap）

> 层级数据的面积占比可视化（>5 个分类时替代饼图）

```javascript
series: [{
  type: 'treemap',
  data: [{
    name: '技术部',
    value: 420,
    children: [
      { name: '前端', value: 150 },
      { name: '后端', value: 180 },
      { name: '测试', value: 90 }
    ]
  }, {
    name: '市场部',
    value: 290,
    children: [
      { name: '品牌', value: 120 },
      { name: '推广', value: 170 }
    ]
  }],
  roam: false,
  nodeClick: 'zoomToNode',
  breadcrumb: { show: true, top: 'bottom' },
  label: {
    show: true,
    formatter: '{b}',
    fontSize: 12
  },
  upperLabel: {
    show: true,
    height: 24,
    color: '#fff',
    fontSize: 13,
    fontWeight: 600
  },
  itemStyle: {
    borderColor: '#fff',
    borderWidth: 2,
    gapWidth: 2
  },
  levels: [
    {
      itemStyle: {
        borderColor: '#333',
        borderWidth: 3,
        gapWidth: 3
      }
    },
    {
      colorSaturation: [0.3, 0.7],
      itemStyle: {
        borderColorSaturation: 0.6,
        gapWidth: 1,
        borderWidth: 1
      }
    }
  ]
}],
labelLayout: { hideOverlap: true }
```
