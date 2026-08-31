# 折线图样式规则

---

## 基础折线图

| 属性 | 值 | 说明 |
| ------ | ----- | ------ |
| type | line | 图表类型 |
| smooth | true | 曲线类型 |
| lineStyle.width | 1 | 折线宽度 1px |
| symbol | emptyCircle | 空心圆形标记 |
| symbolSize | 4 | 标记大小 |

**标签配置**：`show: true, position: top, distance: 5, fontSize: 12, color: #666666`

---

## 面积图

| 属性 | 值 | 说明 |
| ------ | ----- | ------ |
| type | line | 图表类型 |
| smooth | true | 曲线类型 |
| lineStyle.width | 1 | 折线宽度 1px |
| symbol | emptyCircle | 空心圆形标记 |
| symbolSize | 4 | 标记大小 |
| areaStyle.opacity | 0.3 | 面积透明度 |

---

## 模板代码

```javascript
const lineSeriesTemplate = {
  type: 'line',
  smooth: true,
  lineStyle: { width: 1 },
  symbol: 'emptyCircle',
  symbolSize: 4,
  label: {
    show: true,
    position: 'top',
    distance: 5,
    fontSize: 12,
    color: '#666666'
  }
};

const areaSeriesTemplate = {
  ...lineSeriesTemplate,
  areaStyle: { opacity: 0.3 }
};
```
