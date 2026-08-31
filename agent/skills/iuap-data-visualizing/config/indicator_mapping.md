# 指标卡类型映射

---

## 类型定义

| 类型 | 名称 | 图标 | 颜色 | 背景类 | 图标类 |
| ------ | ------ | ------ | ------ | -------- | -------- |
| amount | 金额 | fa-coins | #3293fb | yonbi-vis-card--amount | yonbi-vis-icon--amount |
| volume | 数量 | fa-boxes | #32c4fa | yonbi-vis-card--volume | yonbi-vis-icon--volume |
| profit | 利润 | fa-sack-dollar | #82df2b | yonbi-vis-card--profit | yonbi-vis-icon--profit |
| cost | 成本 | fa-file-invoice-dollar | #fcb530 | yonbi-vis-card--cost | yonbi-vis-icon--cost |
| users | 用户 | fa-users | #737cfd | yonbi-vis-card--users | yonbi-vis-icon--users |
| growth | 增长 | fa-chart-line | #77d83f | yonbi-vis-card--growth | yonbi-vis-icon--growth |
| rate | 比率 | fa-percentage | #1cd46b | yonbi-vis-card--rate | yonbi-vis-icon--rate |
| time | 时间 | fa-clock | #b972fc | yonbi-vis-card--time | yonbi-vis-icon--time |
| sales | 销售 | fa-shopping-cart | #fb6832 | yonbi-vis-card--sales | yonbi-vis-icon--sales |
| inventory | 库存 | fa-warehouse | #fba344 | yonbi-vis-card--inventory | yonbi-vis-icon--inventory |
| customer | 客户 | fa-user-tie | #f6bd4c | yonbi-vis-card--customer | yonbi-vis-icon--customer |

> 颜色定义引用自 [colors/series.md](colors/series.md)
> 背景色定义引用自 [colors/indicator-bg.md](colors/indicator-bg.md)

---

## 关键词识别

根据指标名称中的关键词自动识别类型：

| 类型 | 关键词 |
| ------ | -------- |
| amount | 金额、销售金额、营收、收入、营业额、销售额、钱、元、万元、金额合计 |
| volume | 数量、件数、个数、销量、出货量、订单数、笔数、总数量 |
| profit | 利润、毛利、净利、盈利、收益、毛利润、净利润 |
| cost | 成本、费用、支出、开销、花费、采购成本、运营成本 |
| users | 用户、会员、客户数、活跃用户、新增用户、用户数、人数 |
| growth | 增长、增速、增长率、增幅、增长量、同比增长、环比增长 |
| rate | 率、比率、占比、百分比、转化率、完成率、占比率 |
| time | 时间、天数、小时、时长、周期、工期 |
| sales | 销售、销量、成交、订单、交易、销售额 |
| inventory | 库存、存货、存货量、库存量、备货、仓储 |
| customer | 客户、顾客、买家、消费者、客群 |

---

## 趋势颜色

> 引用自 [colors/trend.md](colors/trend.md)

| 趋势 | 颜色 |
|------|------|
| 上涨 | #fb6832 |
| 下跌 | #1cd46b |
| 持平 | #8c8c8c |

---

## 默认配置

当无法识别类型时使用默认配置：

| 属性 | 值 |
| ------ | ----- |
| 默认类型 | amount |
| 默认图标 | fa-chart-bar |

---

## 类名约束（严重警告）

使用错误类名将导致样式完全错误：

| 必须使用 | 禁止使用 | 说明 |
| --------- | --------- | ------ |
| .yonbi-vis-cards | .data-cards | 容器类名 |
| .yonbi-vis-card__title | .label | 标题类名 |
| .yonbi-vis-card__value | .value | 数值类名 |
| .yonbi-vis-trend > .yonbi-vis-trend__item | .trend（单层） | 趋势结构 |
