# 思维导图（Mindmap）

> 放射状层级信息展示

**实现方式**：使用 ECharts 内置 `tree` series + `radial` 布局。

```javascript
series: [{
  type: 'tree',
  data: [{
    name: '中心主题',
    children: [
      {
        name: '分支1',
        children: [
          { name: '子项1.1' },
          { name: '子项1.2' },
          { name: '子项1.3' }
        ]
      },
      {
        name: '分支2',
        children: [
          { name: '子项2.1' },
          { name: '子项2.2' }
        ]
      },
      {
        name: '分支3',
        children: [
          { name: '子项3.1' },
          { name: '子项3.2' },
          { name: '子项3.3' }
        ]
      }
    ]
  }],
  layout: 'radial',          // 放射状布局
  symbol: 'emptyCircle',
  symbolSize: 7,
  initialTreeDepth: 3,       // 默认展开层级
  animationDurationUpdate: 750,
  label: {
    fontSize: 12,
    color: '#374151'
  },
  leaves: {
    label: {
      fontSize: 11,
      color: '#595959'
    }
  },
  lineStyle: {
    color: '#c9d1d9',
    width: 1.5,
    curveness: 0.5
  },
  emphasis: {
    focus: 'ancestor'        // 高亮时聚焦到祖先链
  }
}],
labelLayout: { hideOverlap: true }
```

### 水平思维导图

```javascript
series: [{
  type: 'tree',
  data: [rootData],
  layout: 'orthogonal',     // 正交布局
  orient: 'LR',             // 从左到右（或 'RL' 从右到左）
  label: { position: 'left', verticalAlign: 'middle', align: 'right' },
  leaves: { label: { position: 'right', align: 'left' } }
}]
```
