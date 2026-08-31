# 其他图表样式规则

---

## 漏斗图

| 属性 | 值 |
| ------ | ----- |
| type | funnel |
| left | 10% |
| top | 60 |
| bottom | 60 |
| width | 80% |
| sort | descending |
| gap | 2 |

**标签配置**：`show: true, position: inside, formatter: {b}: {c}, fontSize: 12`

---

## 仪表盘

| 属性 | 值 |
| ------ | ----- |
| type | gauge |
| center | [50%, 60%] |
| radius | 70% |
| startAngle | 200 |
| endAngle | -20 |
| min | 0 |
| max | 100 |
| splitNumber | 10 |

**轴线颜色分段**：

- [0, 0.3] → #fb6832（橙红）
- [0.3, 0.7] → #fcb530（金黄）
- [0.7, 1] → #1cd46b（翠绿）

---

## 散点图

| 属性 | 值 |
| ------ | ----- |
| type | scatter |
| symbolSize | 10 |
| symbol | circle |

---

## 模板代码

```javascript
const funnelSeriesTemplate = {
  type: 'funnel',
  left: '10%',
  top: 60,
  bottom: 60,
  width: '80%',
  min: 0,
  max: 100,
  minSize: '0%',
  maxSize: '100%',
  sort: 'descending',
  gap: 2,
  label: {
    show: true,
    position: 'inside',
    formatter: '{b}: {c}',
    fontSize: 12
  }
};

const gaugeSeriesTemplate = {
  type: 'gauge',
  center: ['50%', '60%'],
  radius: '70%',
  startAngle: 200,
  endAngle: -20,
  min: 0,
  max: 100,
  splitNumber: 10,
  axisLine: {
    lineStyle: {
      width: 10,
      color: [
        [0.3, '#fb6832'],
        [0.7, '#fcb530'],
        [1, '#1cd46b']
      ]
    }
  }
};
```
