# 指标卡背景色

> 背景色使用 [[series]] 中对应颜色的 rgba 透明版本

---

## 背景色映射

| 类型 | 颜色值 | 背景色 |
| ------ | -------- | -------- |
| amount（金额） | #3293fb | rgba(50, 147, 251, 0.1) |
| volume（数量） | #32c4fa | rgba(50, 196, 250, 0.1) |
| profit（利润） | #82df2b | rgba(130, 223, 43, 0.1) |
| cost（成本） | #fcb530 | rgba(252, 181, 48, 0.1) |
| sales（销售） | #fb6832 | rgba(251, 104, 50, 0.1) |
| users（用户） | #737cfd | rgba(115, 124, 253, 0.1) |
| rate（比率） | #1cd46b | rgba(28, 212, 107, 0.1) |
| time（时间） | #b972fc | rgba(185, 114, 252, 0.1) |
| growth（增长） | #77d83f | rgba(119, 216, 63, 0.1) |
| inventory（库存） | #fba344 | rgba(251, 163, 68, 0.1) |
| customer（客户） | #f6bd4c | rgba(246, 189, 76, 0.1) |

---

## CSS 样式类

```css
.yonbi-vis-card--amount { background: rgba(50, 147, 251, 0.1); }
.yonbi-vis-card--volume { background: rgba(50, 196, 250, 0.1); }
.yonbi-vis-card--profit { background: rgba(130, 223, 43, 0.1); }
.yonbi-vis-card--cost { background: rgba(252, 181, 48, 0.1); }
.yonbi-vis-card--sales { background: rgba(251, 104, 50, 0.1); }
.yonbi-vis-card--users { background: rgba(115, 124, 253, 0.1); }
.yonbi-vis-card--rate { background: rgba(28, 212, 107, 0.1); }
.yonbi-vis-card--time { background: rgba(185, 114, 252, 0.1); }
.yonbi-vis-card--growth { background: rgba(119, 216, 63, 0.1); }
.yonbi-vis-card--inventory { background: rgba(251, 163, 68, 0.1); }
.yonbi-vis-card--customer { background: rgba(246, 189, 76, 0.1); }
```
