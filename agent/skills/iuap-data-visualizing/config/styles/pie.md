# 饼图样式规则

---

## 基础饼图

| 属性 | 值 | 说明 |
| ------ | ----- | ------ |
| type | pie | 图表类型 |
| center | [50%, 50%] | 圆心居中 |
| radius | 60% | 半径比例 |
| avoidLabelOverlap | true | 防止标签重叠 |
| borderRadius | 3 | 扇区圆角 |
| borderColor | #fff | 扇区边框色 |
| borderWidth | 2 | 扇区边框宽度 |

**标签配置**：`show: true, position: outside, formatter: {b}\n{d}%, fontSize: 12, color: inherit`

**标签线配置**：`show: true, length: 10, length2: 10`

---

## 环图

| 属性 | 值 | 说明 |
| ------ | ----- | ------ |
| type | pie | 图表类型 |
| center | [50%, 50%] | 圆心居中 |
| radius | [40%, 60%] | 内径40%，外径60% |
| avoidLabelOverlap | true | 防止标签重叠 |

**其他配置同饼图**

---

## 模板代码

```javascript
const pieSeriesTemplate = {
  type: 'pie',
  center: ['50%', '50%'],
  radius: '60%',
  avoidLabelOverlap: true,
  label: {
    show: true,
    position: 'outside',
    formatter: '{b}\n{d}%',
    fontSize: 12,
    color: 'inherit'
  },
  labelLine: {
    show: true,
    length: 10,
    length2: 10
  },
  itemStyle: {
    borderRadius: 3,
    borderColor: '#fff',
    borderWidth: 2
  }
};

const donutSeriesTemplate = {
  ...pieSeriesTemplate,
  radius: ['40%', '60%']
};
```
