# 指标卡生成规范

## 输出模式

| 模式 | 说明 | 使用场景 | 模板文件 |
| ------ | ------ | --------- | --------- |
| standalone | 独立页面，输出完整 HTML 文件 | 用户单独请求指标卡/看板时 | [templates/indicator/card.html](../templates/indicator/card.html) |
| fragment | 片段模式，仅输出卡片 HTML 片段 | 供 iuap-data-reporting 技能嵌入报告时 | [templates/indicator/fragment.html](../templates/indicator/fragment.html) |

模式选择：用户直接请求 → standalone；iuap-data-reporting 调用 → fragment；未指定 → standalone

## 指标类型自动识别

详见 → [references/indicator_types.md](indicator_types.md)
默认类型：无法识别时使用 amount（主蓝 #3293fb）

## 颜色约束

所有指标卡颜色必须从 11 艰系列中选择 → [config/colors.json](../config/colors.json)
卡片背景：rgba 透明版本（opacity: 0.1）
图标背景：系列色实色
趋势颜色：上涨=#fb6832，下跌=#1cd46b

## 数据结构

```json
{
  "CARD_TITLE": "销售数据看板",
  "CARD_LIST": [
    {
      "cardClass": "yonbi-vis-card--amount",
      "iconBgClass": "yonbi-vis-icon--amount",
      "iconClass": "fa-coins",
      "title": "销售金额",
      "value": "¥63.70万",
      "hasTrend": true,
      "yoy": { "label": "同比", "value": "23.68%", "trendUp": true },
      "mom": { "label": "环比", "value": "10%", "trendDown": true }
    }
  ]
}
```

## 数值格式化规则

| 类型 | 规则 | 示例 |
| ------ | ------ | ------ |
| 金额 | ≥1万显示"X.XX万" | ¥63.70万 |
| 数量 | 千分位分隔 | 23,725 |
| 百分比 | 保留1-2位小数 | 23.68% |

详细规则见 → [config/value_format.json](../config/value_format.json)

## 卡片数量与布局

| 数量 | 布局方式 |
| ------ | --------- |
| 1-3 个 | 自适应网格，单行排列 |
| 4-6 个 | 2-3 列网格 |
| 7-12 个 | 3-4 列网格 |
| >12 个 | 建议分组或精简 |

## HTML 结构（fragment 模式）

完整 HTML 样例见 → [templates/indicator/fragment.html](../templates/indicator/fragment.html)

核心结构：

```html
<div class="yonbi-vis-card yonbi-vis-card--amount">
  <div class="yonbi-vis-card__header">
    <div class="yonbi-vis-icon-bg yonbi-vis-icon--amount"><i class="fa fa-coins yonbi-vis-card__icon"></i></div>
    <div class="yonbi-vis-card__title">销售金额</div>
  </div>
  <div class="yonbi-vis-card__value">¥63.70<span class="yonbi-vis-card__unit">万</span></div>
  <div class="yonbi-vis-trend">
    <div class="yonbi-vis-trend__item">
      <span class="yonbi-vis-trend__label">同比</span>
      <span class="yonbi-vis-trend--up"><i class="fa fa-arrow-up"></i>23.68%</span>
    </div>
  </div>
</div>
```

图标嵌套规则：`yonbi-vis-card__icon` 必须嵌套在 `yonbi-vis-icon-bg` 内部，禁止并列。
单位样式规则：单位（万、亿等）使用 `<span class="yonbi-vis-card__unit">` 包裹，字号与标题一致（15px）。

## 类名约束

| 必须使用 ✅ | 禁止使用 ❌ | 说明 |
| ------------ | ------------ | ------ |
| yonbi-vis-cards | data-cards | 容器类名 |
| yonbi-vis-card__title | label | 标题类名 |
| yonbi-vis-card__value | value | 数值类名 |
| yonbi-vis-card__unit | unit | 单位样式（字号与标题一致） |
| yonbi-vis-trend > yonbi-vis-trend__item | trend（单层） | 趋势结构 |

## 趋势样式

| 类名 | 颜色 | 说明 |
| ------ | ------ | ------ |
| yonbi-vis-trend--up | #fb6832（橙红） | 上涨 |
| yonbi-vis-trend--down | #1cd46b（翠绿） | 下跌 |
| yonbi-vis-trend--neutral | #8c8c8c（灰色） | 持平 |

## 关键样式参数

| 属性 | 值 |
| ------ | ----- |
| min-height | 140px |
| yonbi-vis-card__value font-size | 24px |
| yonbi-vis-trend gap | 32px |
| yonbi-vis-icon-bg width/height | 20px |
| yonbi-vis-icon-bg border-radius | 6px |
| yonbi-vis-card__icon font-size | 10px |
