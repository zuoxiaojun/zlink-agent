# 雷达图样式规则

---

## 基础配置

| 属性 | 值 | 说明 |
| ------ | ----- | ------ |
| type | radar | 图表类型 |
| symbol | emptyCircle | 空心圆形标记 |
| symbolSize | 4 | 标记大小 |
| lineStyle.width | 1 | 线宽 |
| areaStyle.opacity | 0.3 | 面积透明度 |

---

## radar 坐标系配置

| 属性 | 值 | 说明 |
| ------ | ----- | ------ |
| shape | polygon | 多边形 |
| splitNumber | 5 | 分割层数 |
| axisName.color | #666 | 维度名称颜色 |
| axisName.fontSize | 12 | 维度名称字号 |

---

## 模板代码

```javascript
const radarSeriesTemplate = {
  type: 'radar',
  symbol: 'emptyCircle',
  symbolSize: 4,
  lineStyle: { width: 1 },
  areaStyle: { opacity: 0.3 }
};

const radarOptionTemplate = {
  radar: {
    shape: 'polygon',
    splitNumber: 5,
    axisName: { color: '#666', fontSize: 12 },
    splitLine: { lineStyle: { color: '#e5e7eb' } },
    splitArea: {
      show: true,
      areaStyle: { color: ['rgba(50,147,251,0.05)', 'rgba(50,147,251,0.1)'] }
    },
    axisLine: { lineStyle: { color: '#e5e7eb' } }
  }
};
```
