# 旭日图（Sunburst）

> 多层级占比的可视化，是饼图的多层扩展

```javascript
series: [{
  type: 'sunburst',
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
  radius: ['15%', '80%'],
  sort: null,                // 保持原始顺序
  emphasis: { focus: 'ancestor' },
  levels: [
    {},                      // 第0层默认
    {
      r0: '15%', r: '40%',
      itemStyle: { borderWidth: 2 },
      label: { rotate: 'tangential', fontSize: 12, color: '#fff' }
    },
    {
      r0: '40%', r: '70%',
      label: { align: 'right', fontSize: 11 }
    }
  ],
  itemStyle: { borderRadius: 3 }
}],
labelLayout: { hideOverlap: true }
```
