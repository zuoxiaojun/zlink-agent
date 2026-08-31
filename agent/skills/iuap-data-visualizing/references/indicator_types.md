# 指标类型识别与映射规则

## 类型识别流程

```
指标名称 → 关键词匹配 → 确定类型 → 获取类名/颜色/图标
无法匹配 → 使用默认类型 (amount)
```

## 类型映射表

| 类型 | 名称 | card_class | icon_class | 颜色 | 颜色索引 |
| ------ | ------ | ------------ | ------------ | ------ | --------- |
| amount | 金额 | `yonbi-vis-card--amount` | `fa-coins` | #3293fb | 0 |
| volume | 数量 | `yonbi-vis-card--volume` | `fa-boxes` | #32c4fa | 2 |
| profit | 利润 | `yonbi-vis-card--profit` | `fa-sack-dollar` | #82df2b | 1 |
| cost | 成本 | `yonbi-vis-card--cost` | `fa-file-invoice-dollar` | #fcb530 | 3 |
| sales | 销售 | `yonbi-vis-card--sales` | `fa-shopping-cart` | #fb6832 | 4 |
| users | 用户 | `yonbi-vis-card--users` | `fa-users` | #737cfd | 5 |
| rate | 比率 | `yonbi-vis-card--rate` | `fa-percentage` | #1cd46b | 6 |
| time | 时间 | `yonbi-vis-card--time` | `fa-clock` | #b972fc | 7 |
| growth | 增长 | `yonbi-vis-card--growth` | `fa-chart-line` | #77d83f | 8 |
| inventory | 库存 | `yonbi-vis-card--inventory` | `fa-warehouse` | #fba344 | 9 |
| customer | 客户 | `yonbi-vis-card--customer` | `fa-user-tie` | #f6bd4c | 10 |

## 关键词匹配规则

| 类型 | 匹配关键词 |
| ------ | ----------- |
| amount | 金额、销售金额、营收、收入、营业额、销售额、钱、元、万元、金额合计 |
| volume | 数量、件数、个数、销量、出货量、订单数、笔数、总数量 |
| profit | 利润、毛利、净利、盈利、收益、毛利润、净利润 |
| cost | 成本、费用、支出、开销、花费、采购成本、运营成本 |
| sales | 销售、销量、成交、订单、交易、销售额 |
| users | 用户、会员、客户数、活跃用户、新增用户、用户数、人数 |
| rate | 率、比率、占比、百分比、转化率、完成率、占比率 |
| time | 时间、天数、小时、时长、周期、工期 |
| growth | 增长、增速、增长率、增幅、增长量、同比增长、环比增长 |
| inventory | 库存、存货、存货量、库存量、备货、仓储 |
| customer | 客户、顾客、买家、消费者、客群 |

## 默认配置

无法匹配时使用：类型=amount，card_class=`yonbi-vis-card--amount`，icon_class=`fa-chart-bar`，颜色=#3293fb

## 类名使用规则

卡片容器：`<div class="yonbi-vis-card yonbi-vis-card--{type}">`
图标背景：`<div class="yonbi-vis-icon-bg yonbi-vis-icon--{type}"><i class="fa {icon_class} yonbi-vis-card__icon"></i></div>`

## 颜色使用规则

卡片背景：系列色的 rgba 透明版本（opacity: 0.1）
图标背景：系列色实色
趋势颜色：上涨=#fb6832（yonbi-vis-trend--up），下跌=#1cd46b（yonbi-vis-trend--down），持平=#8c8c8c（yonbi-vis-trend--neutral）

完整配置见：[config/indicator_mapping.json](../config/indicator_mapping.json)
