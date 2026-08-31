# 趋势颜色

> 引用自 [[series]] 中的颜色定义

---

## 趋势颜色规则

| 趋势 | 颜色 | 颜色值 | 说明 |
|------|------|--------|------|
| 上涨 | 橙红 | #fb6832 | 同比/环比上升 |
| 下跌 | 翠绿 | #1cd46b | 同比/环比下降 |
| 持平 | 灰色 | #8c8c8c | 无变化 |

> 采用中国市场惯例：上涨=红色系，下跌=绿色系

---

## CSS 类名

| 趋势 | 类名 | 图标 |
|------|------|------|
| 上涨 | yonbi-vis-trend--up | fa-arrow-up |
| 下跌 | yonbi-vis-trend--down | fa-arrow-down |
| 持平 | yonbi-vis-trend--neutral | fa-minus |

---

## 使用示例

```html
<span class="yonbi-vis-trend--up"><i class="fa fa-arrow-up"></i>23.68%</span>
<span class="yonbi-vis-trend--down"><i class="fa fa-arrow-down"></i>5.32%</span>
```
