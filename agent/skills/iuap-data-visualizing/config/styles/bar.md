# 柱状图样式规则

---

## 基础柱状图（垂直）

| 属性 | 值 | 说明 |
| ------ | ----- | ------ |
| type | bar | 图表类型 |
| barCategoryGap | 70% | 类目间距 |
| barBorderRadius | [3, 3, 0, 0] | 圆角（柱顶两角） |
| 渐变方向 | 垂直（0度） | 从上到下 |
| 渐变 | 系列色(100%) → 系列色(70%透明度) | - |

**标签配置**：`show: true, position: top, distance: 5, fontSize: 12, color: #666666`

---

## 条形图（横向柱图）

| 属性 | 值 | 说明 |
| ------ | ----- | ------ |
| type | bar | 图表类型 |
| barCategoryGap | 70% | 类目间距 |
| barBorderRadius | [0, 3, 3, 0] | 圆角（右侧两角） |
| 渐变方向 | 水平（90度） | 从左到右 |
| 渐变 | 系列色(70%透明度) → 系列色(100%) | - |

**标签配置**：`show: true, position: right, distance: 5, fontSize: 12, color: #666666`

---

## 柱线组合图

**柱图部分**：同基础柱状图配置

**折线部分**：同折线图配置

**注意**：组合图属于多系列，标签默认隐藏

---

## 模板代码

```javascript
const barSeriesTemplate = {
  type: 'bar',
  barCategoryGap: '70%',
  itemStyle: {
    barBorderRadius: [3, 3, 0, 0]
  },
  label: {
    show: true,
    position: 'top',
    distance: 5,
    fontSize: 12,
    color: '#666666'
  }
};

// 渐变色生成
function generateGradientColor(seriesColor) {
  const hex = seriesColor.replace('#', '');
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);
  return {
    type: 'linear',
    x: 0, y: 0, x2: 0, y2: 1,
    colorStops: [
      { offset: 0, color: seriesColor },
      { offset: 1, color: `rgba(${r},${g},${b},0.7)` }
    ]
  };
}
```
