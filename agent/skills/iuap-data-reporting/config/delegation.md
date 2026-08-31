# 委托协议规则

> 本规则定义报告技能向可视化技能委托图表生成的协议。

---

## 委托接口

```json
{
  "skill": "iuap-data-visualizing",
  "requests": [
    {"id": "indicator-cards", "type": "indicator-card", "data": {"cards": [...]},
    {"id": "chart-trend", "analysisPurpose": "趋势分析", "data": {...}, "context": {...}}
  ]
}
```

---

## 请求项结构

| 字段 | 类型 | 必填 | 说明 |
| ------ | ------ | ------ | ------ |
| id | string | 是 | 唯一标识，用于输出匹配 |
| analysisPurpose | string | 图表必填 | 趋势分析/分类对比/占比构成/相关性分析/分布分析/排名分析/漏斗分析/多维评估 |
| type | string | 指标卡必填 | 固定为 "indicator-card" |
| data | object | 是 | 图表数据或指标卡数据 |
| context | object | 否 | 标题、容器ID等上下文 |

---

## 指标卡委托

**必须先读取**：[../iuap-data-visualizing/templates/indicator/fragment.html](../iuap-data-visualizing/templates/indicator/fragment.html)

**指标类型识别规则** → [../iuap-data-visualizing/config/indicator_mapping.md](../iuap-data-visualizing/config/indicator_mapping.md)

### 请求项示例

```json
{
  "id": "indicator-cards",
  "type": "indicator-card",
  "data": {
    "cards": [
      {
        "cardClass": "yonbi-vis-card--amount",
        "iconBgClass": "yonbi-vis-icon--amount",
        "iconClass": "fa-coins",
        "title": "销售金额",
        "value": "¥63.70<span class=\"yonbi-vis-card__unit\">万</span>",
        "hasTrend": true,
        "yoy": {"label": "同比", "value": "23.68%", "trendUp": true}
      }
    ]
  }
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
| ------ | ------ | ------ | ------ |
| cardClass | string | 是 | 卡片类型样式类名，见 indicator_mapping.md |
| iconBgClass | string | 是 | 图标背景样式类名，见 indicator_mapping.md |
| iconClass | string | 是 | FontAwesome 图标类名 |
| title | string | 是 | 指标名称 |
| value | string | 是 | 指标数值，**支持 HTML**，单位用 `<span class="yonbi-vis-card__unit">` 包裹 |
| hasTrend | boolean | 否 | 是否展示趋势，默认 false |
| yoy | object | 否 | 同比：{label, value, trendUp} |
| mom | object | 否 | 环比：{label, value, trendUp} |
| qoq | object | 否 | 季环比：{label, value, trendUp} |

### 趋势对象字段

| 字段 | 类型 | 说明 |
| ------ | ------ | ------ |
| label | string | 趋势标签，如"同比"、"环比" |
| value | string | 趋势数值，如"23.68%" |
| trendUp | boolean | true=上涨(橙红)，false=下跌(翠绿) |

### 单位样式规则

单位（万、亿等）使用 `<span class="yonbi-vis-card__unit">` 包裹，字号与标题一致（15px）。

---

## 分析目的映射

| 分析目的 | 可视化技能自动选择 |
| ---------- | ------------------- |
| 趋势分析 | line / area / bar |
| 分类对比 | bar |
| 占比构成 | pie / donut / treemap |
| 相关性分析 | scatter / bubble |
| 分布分析 | histogram / boxplot |
| 排名分析 | 水平 bar |
| 漏斗分析 | funnel / waterfall |
| 多维评估 | radar |

---

## 禁止事项

- ❌ 禁止指定具体图表类型（如 "line"、"pie"）
- ❌ 禁止定义图表样式
- ❌ 禁止自定义主题或颜色
- ❌ 禁止覆盖可视化技能的选型决策

---

## 响应处理

**铁律**：报告技能最终输出 **HTML 文件或代码块**，不是 JSON！

---

## 委托返回格式（可视化技能必须遵守）

可视化技能返回的每个图表必须包含：

### 返回结构

```json
{
  "id": "chart-trend",
  "html": {
    "container": "<div id=\"chart-trend\" class=\"yonbi-rep-chart\"><div class=\"yonbi-rep-loading\">图表渲染中...</div></div>",
    "script": "<script>...完整的内联脚本...</script>"
  }
}
```

### 脚本必须包含的内容

| 内容 | 说明 | 禁止行为 |
| ------ | ------ | --------- |
| **公共函数** | `formatUnified`、`safeGetValue`、`calcAdaptiveGrid` 等必须内联 | ❌ 禁止省略、禁止简化 |
| **label.formatter** | 必须使用 `formatUnified(safeGetValue(params), false)` | ❌ 禁止手写 `p.value / 10000` 等 |
| **yAxis.axisLabel.formatter** | 必须使用 `formatUnified(value, true)` | ❌ 禁止手写简化版 |
| **grid** | 必须使用 `calcAdaptiveGrid` 计算或完整配置 | ❌ 禁止手写固定值 |

---

## 报告技能嵌入规则（强制）

| 规则 | 说明 |
| ------ | ------ |
| **原样嵌入** | 将可视化技能返回的 `html.container` 和 `html.script` 原样嵌入报告 |
| **禁止修改** | 不得修改脚本内容、不得删除公共函数、不得简化 option |
| **禁止自行编写** | 不得自行编写 label.formatter、yAxis.axisLabel、grid 等配置 |

---

## 组装逻辑

**输入**：可视化技能返回的图表配置（JSON 格式）

**输出**：报告技能组装后的 **HTML 文件或代码块**

**组装步骤**：

1. 提取指标卡 HTML，嵌入报告指标卡区域
2. 遍历图表配置，按章节顺序输出：容器 HTML + 内联脚本
3. 在报告底部输出全局脚本（resize 监听）

---

## 完整示例

**完整批量委托示例** → [templates/report/sections.md](templates/report/sections.md)
