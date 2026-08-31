# 韦恩图（Venn）

> 展示 2-3 个集合之间的交并差关系

**实现原理**：ECharts `custom` renderItem 绘制半透明圆形叠加。

### 2 集合韦恩图

```javascript
series: [{
  type: 'custom',
  coordinateSystem: 'none',  // 不使用坐标系
  renderItem: function(params, api) {
    return {
      type: 'group',
      children: [
        // 左圆
        {
          type: 'circle',
          shape: { cx: 280, cy: 200, r: 120 },
          style: { fill: 'rgba(50,147,251,0.3)', stroke: '#3293fb', lineWidth: 2 }
        },
        // 右圆
        {
          type: 'circle',
          shape: { cx: 380, cy: 200, r: 120 },
          style: { fill: 'rgba(255,77,79,0.3)', stroke: '#ff4d4f', lineWidth: 2 }
        },
        // 左侧标签
        {
          type: 'text',
          style: { text: '集合 A', x: 220, y: 195, fill: '#3293fb', fontSize: 14, fontWeight: 600 }
        },
        // 右侧标签
        {
          type: 'text',
          style: { text: '集合 B', x: 420, y: 195, fill: '#ff4d4f', fontSize: 14, fontWeight: 600 }
        },
        // 交集标签
        {
          type: 'text',
          style: { text: 'A ∩ B', x: 310, y: 195, fill: '#722ed1', fontSize: 13, fontWeight: 600, textAlign: 'center' }
        }
      ]
    };
  },
  data: [0],  // 必须有一条数据触发渲染
  animation: false
}],
labelLayout: { hideOverlap: true }  // custom 系列：手动控制标签位置避免重叠
```

### 3 集合韦恩图

```javascript
// 三个圆心呈等边三角形排列
const cx = 330, cy = 200, r = 110, offset = 80;
// 圆1：(cx, cy - offset)
// 圆2：(cx - offset * Math.cos(30°), cy + offset * Math.sin(30°))
// 圆3：(cx + offset * Math.cos(30°), cy + offset * Math.sin(30°))
// 各圆颜色：rgba(50,147,251,0.25) / rgba(255,77,79,0.25) / rgba(82,196,26,0.25)
// 交集区域：A∩B / A∩C / B∩C / A∩B∩C 各加 text 标签
```

### 数据标签位置计算

```javascript
// 2 集合：仅A在左圆心偏左，仅B在右圆心偏右，A∩B在两圆心中间
// 3 集合：仅A/B/C在各圆心方向偏移，两两交集在两圆心中点，三交集在中心
```
