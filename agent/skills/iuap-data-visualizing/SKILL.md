---
name: iuap-data-visualizing
description: >-
  纯图表生成技能。仅负责图表生成，不生成分析文字或报告。将数据转换为可运行的 HTML 图表产物，支持柱状图、折线图、饼图、散点图、雷达图、桑基图、词云、指标卡、信息图、组织架构图等 20+ 种图表类型。
  当用户或其他技能需要生成 ECharts 图表、指标卡等可视化产物时使用。ECharts 图表生成必须委托此技能执行。
  不适用于需要深度分析或完整图文报告的场景（请使用 iuap-data-reporting）。    
metadata:
  yonbip:
    version: 15.14.3
---

# 纯图表生成技能

**定位**：给我数据，我给你一张可运行的图表 HTML。

---

## 硬约束（不变量）

以下不变量对所有图表强制生效，无论使用何种实现方式（函数调用或手写 option）：

| 不变量 | 说明 |
| ------- | ------ |
| **数据真实性** | 所有图表数据必须来自用户明确提供的内容。无数据 = 不画图 |
| **输出格式** | 默认产物为 .html 文件并回传路径；仅当用户明确要求代码块形式时，才以单个 ```html 代码块输出，此时禁止调用 Write 工具落盘。不生成报告、不生成分析、不生成长文 |
| **系列色** | ECharts series 必须走 11 色板——第 1 个系列用 `#3293fb`，多系列按顺序补位。图例色必须与系列色一致。非数据元素（连线/辅助文字灰色系）和语义化场景（正负值/集合区分）不受此约束。完整规则见 [config/colors/series.md](config/colors/series.md) |
| **数值格式化** | Y轴、tooltip、label 三处必须用 `formatUnified`，确保单位一致。详见 [config/logic/base.md](config/logic/base.md) |
| **类目取值** | dataset 模式下用 `params[0].value[0]`，非 dataset 模式用 `params.name` |
| **主题约束** | 原样使用提供的主题信息，禁止精简、修改 |
| **标签防重叠** | 含 label 的图表必须设 `labelLayout: { hideOverlap: true }`。L1 函数已内置；L2/L3 手动加。详见 [config/logic/label-display.md](config/logic/label-display.md) |
| **指标卡图标** | 所有指标卡必须有图标，从 [config/indicator_mapping.md](config/indicator_mapping.md) 选择 |

## 实现层级（按图表类型选择）

| 层级 | 适用场景 | 机制 | 自由度 |
| ------ | --------- | ------ | -------- |
| **L1 高层函数** | 柱/线/饼/雷达/散点/双轴（~80% 业务图表） | 调用 `create*Option` 一行生成 option | 低，函数管控色值与样式 |
| **L2 组装函数** | L1 类型的变体（堆叠/百分比/带标注等） | `generate*Series` 生成 series + 手写外壳 | 中，系列色走函数，外壳手写 |
| **L3 逃生口** | custom/tree/sankey/wordcloud/liquidfill 等特殊图表 | 手写 option + 遵守上方不变量 | 高，但色值/数据/格式化必须合规 |

**L1 函数**：`createCartesianOption` / `createHorizontalCartesianOption` / `createScatterOption` / `createDualAxisOption` / `createNonCartesianOption`（见 [templates/echarts/](templates/echarts/)）

**L2 函数**：`generateBarSeries` / `generateLineSeries` / `generateAreaSeries` / `generateHorizontalBarSeries` / `generatePieSeries` / `generateDonutSeries` / `generateRadarSeries`

**L3 示例**：[references/recipes/](references/recipes/) 下的 15 个配方均为合规手写 option，LLM 可照抄并按不变量调整。

---

## 核心流程

```
步骤1：数据获取（以用户意图为准，无固定优先级顺序）
├── 上下文中已有数据 → 直接使用
├── 用户上传/指定文件 → 调用 iuap-data-file-io 或 Read 工具读取
├── 无数据但有查询意图 → 调用 iuap-data-querying 技能查询
└── 无数据且无查询意图 → 告知用户需要提供数据

【判断】数据是否满足图表需求？
├── 满足 → 直接使用
└── 不足（缺少计算字段）→ 用 Python 或查询工具计算，禁止自行执行任何算术运算或单位换算

步骤2：智能选型
├── 用户指定图表类型 → 使用指定类型
└── 未指定 → 根据数据特征自动选择（见下方选型规则）

步骤3：加载规则文件（强制）
│
├── 【必读】基础规则（所有图表必须加载，3个文件）
│   ├── [config/layout/base.md](config/layout/base.md)     → 标题、图例、grid、容器
│   ├── [config/logic/base.md](config/logic/base.md)       → 数值格式化
│   └── [config/logic/dataset.md](config/logic/dataset.md) → dataset 模式规则
│
├── 【必读】样式规则（根据图表类型加载）
│   ├── 柱状图/条形图 → [config/styles/bar.md](config/styles/bar.md)
│   ├── 折线图/面积图 → [config/styles/line.md](config/styles/line.md)
│   ├── 饼图/环图 → [config/styles/pie.md](config/styles/pie.md)
│   ├── 雷达图 → [config/styles/radar.md](config/styles/radar.md)
│   ├── 指标卡 → [config/styles/indicator.md](config/styles/indicator.md)
│   └── 其他图表 → [config/styles/other.md](config/styles/other.md)
│
└── 【按需】逻辑规则
    └── 多系列图表 → [config/logic/label-display.md](config/logic/label-display.md)

步骤4：生成输出
│
├── 【必读】加载模板函数（内联到 HTML 中）
│   ├── [templates/echarts/common.js](templates/echarts/common.js) → formatUnified、safeGetValue、calcAdaptiveGrid、gridTemplate
│   └── [templates/echarts/option_cartesian.js](templates/echarts/option_cartesian.js) → createCartesianOption、createHorizontalCartesianOption、createScatterOption
│
├── 构建数据源
│   ├── L1/L2 图表（柱/线/饼/雷达/散点/双轴）：dataset 模式，构建二维数组 [['类目', '指标1'], ['A', 100], ...]
│   └── L3 特殊图表（custom/tree/sankey/wordcloud/liquidfill）：series.data 原生模式，见 references/recipes/
│
├── 调用模板函数生成 option（L1/L2 场景）
│   ├── 方式1（垂直柱图/折线）：调用 createCartesianOption(title, legendData, datasetSource, seriesConfig)
│   ├── 方式1（横向条图/排名图）：调用 createHorizontalCartesianOption(title, legendData, datasetSource, seriesConfig)
│   ├── 方式1（散点图/气泡图）：调用 createScatterOption(title, datasetSource, xName, yName, seriesConfig)
│   ├── 方式1（双轴图/柱+线组合）：调用 createDualAxisOption(title, legendData, datasetSource, seriesConfig, yAxisConfig)
│   └── 方式2：series 只声明 type，样式由模板函数统一处理
│
└── L3 场景：手写 option + 遵守不变量（参考 references/recipes/ 下的合规示例）
│
└── 按硬约束表·输出格式规则执行（默认 .html 文件；用户明确要求代码块时输出代码块）
    ├── ECharts 图表 → [templates/echarts/base.html](templates/echarts/base.html)
    ├── 指标卡 → [templates/indicator/card.html](templates/indicator/card.html)
    └── 信息图 → [templates/infographic/base.html](templates/infographic/base.html)
```

---

## 规则引用约束

**详细规则** → [config/layout/base.md](config/layout/base.md#六常见错误对照表)

包含：标题配置、图例配置、Grid 配置、容器配置、常见错误对照表

---

## 图表选型规则

| 数据特征 | 推荐图表 |
| --------- | --------- |
| 时间序列 | line、area、candlestick |
| 分类比较 | bar、pictorialBar |
| 占比/构成 | pie（≤5类）、donut（5-7类）、treemap（>7类）、sunburst（多层级） |
| 相关性 | scatter、bubble |
| 多维评估 | radar、parallel |
| 统计分布 | boxplot、violin、histogram |
| 流向/关系 | sankey、graph、chord |
| 层级结构 | tree、treemap、sunburst |
| 地理空间 | map、geo |
| 进度/完成率 | gauge、liquidFill |
| 漏斗转化 | funnel、waterfall |
| 集合关系 | venn |
| 因果分析 | fishbone |
| 文本频率 | wordCloud |

详细规则 → [config/charts.md](config/charts.md)

---

## 规则文件索引

### 基础规则（所有图表必读）

| 文件 | 内容 |
| ------ | ------ |
| [layout/base.md](config/layout/base.md) | 标题、图例、grid、容器（合并文件） |
| [logic/base.md](config/logic/base.md) | 数值格式化（合并文件） |
| [logic/dataset.md](config/logic/dataset.md) | dataset 模式规则：安全取值、数据格式、完整示例 |

### 样式规则（按图表类型加载）

| 文件 | 内容 |
| ------ | ------ |
| [styles/bar.md](config/styles/bar.md) | 柱状图：barCategoryGap、barBorderRadius、渐变 |
| [styles/line.md](config/styles/line.md) | 折线图：smooth、lineStyle、symbol |
| [styles/pie.md](config/styles/pie.md) | 饼图：center、radius、labelLine |
| [styles/radar.md](config/styles/radar.md) | 雷达图：shape、splitNumber |
| [styles/indicator.md](config/styles/indicator.md) | 指标卡：类名、尺寸、HTML结构 |
| [styles/other.md](config/styles/other.md) | 漏斗图、仪表盘、散点图 |

### 逻辑规则（按需加载）

| 文件 | 内容 | 何时加载 |
| ------ | ------ | --------- |
| [logic/label-display.md](config/logic/label-display.md) | 自动防重叠：labelLayout.hideOverlap | 多系列图表 |
| [logic/special-value.md](config/logic/special-value.md) | null/NaN 处理 | 有特殊值 |
| [logic/dataset-stacked.md](config/logic/dataset-stacked.md) | 三维数据堆叠柱图 | 三维单指标场景 |

### 颜色规则（所有图表必读）

| 文件 | 内容 |
| ------ | ------ |
| [colors/series.md](config/colors/series.md) | 11 色系列（真理源） |
| [colors/trend.md](config/colors/trend.md) | 趋势颜色：上涨/下跌 |
| [colors/indicator-bg.md](config/colors/indicator-bg.md) | 指标卡背景色 |

**系列色约束**：ECharts 图表的 series 必须走 11 色板——第 1 个系列（主体色）用 `#3293fb`，多系列按顺序补位。非数据元素（连线、辅助文字等灰色系）和语义化场景（正/负值、集合区分）不受此约束。完整规则见 [config/colors/series.md](config/colors/series.md)。

---

## 指标卡生成

**必须先读取** [config/styles/indicator.md](config/styles/indicator.md) 获取完整样式规则。

关键约束：

- 类名：`.yonbi-vis-cards`、`.yonbi-vis-card`、`.yonbi-vis-icon-bg`、`.yonbi-vis-card__title`、`.yonbi-vis-card__value`
- 尺寸：图标容器 20px×20px，标题字号 15px，数值字号 24px
- 图标映射 → [config/indicator_mapping.md](config/indicator_mapping.md)

---

## 多图布局

| 图表数量 | 布局方式 |
| --------- | --------- |
| 1 | 单图居中，最大宽度 900px |
| 2 | 2 列布局 |
| 3-4 | 2×2 网格 |
| ≥5 | 自适应网格布局 |

---

## 特殊图表配方

| 图表 | 配方文件 | 需要插件 |
| ------ | --------- | --------- |
| 瀑布图 | [recipes/waterfall.md](references/recipes/waterfall.md) | 否 |
| 韦恩图 | [recipes/venn.md](references/recipes/venn.md) | 否 |
| 鱼骨图 | [recipes/fishbone.md](references/recipes/fishbone.md) | 否 |
| 小提琴图 | [recipes/violin.md](references/recipes/violin.md) | 否 |
| 思维导图 | [recipes/mindmap.md](references/recipes/mindmap.md) | 否 |
| 词云 | [recipes/wordcloud.md](references/recipes/wordcloud.md) | 是 |
| 水球图 | [recipes/liquidfill.md](references/recipes/liquidfill.md) | 是 |
| 旭日图 | [recipes/sunburst.md](references/recipes/sunburst.md) | 否 |
| 矩形树图 | [recipes/treemap.md](references/recipes/treemap.md) | 否 |
| 桑基图 | [recipes/sankey.md](references/recipes/sankey.md) | 否 |

---

## 模板文件

| 文件 | 用途 |
| ------ | ------ |
| [templates/echarts/base.html](templates/echarts/base.html) | ECharts HTML 外壳 |
| [templates/echarts/common.js](templates/echarts/common.js) | 公共函数：formatUnified、safeGetValue、calcAdaptiveGrid、measureTextWidth、shortenNumber、seriesColors |
| [templates/echarts/option_cartesian.js](templates/echarts/option_cartesian.js) | 直角坐标系：createCartesianOption（垂直柱图/折线）、createHorizontalCartesianOption（横向条图/排名图）、createScatterOption（散点图/气泡图）、createDualAxisOption（双轴图/柱+线组合） |
| [templates/echarts/option_non_cartesian.js](templates/echarts/option_non_cartesian.js) | 非直角坐标系：createNonCartesianOption 函数 |
| [templates/indicator/card.html](templates/indicator/card.html) | 指标卡独立页面模板 |
| [templates/indicator/fragment.html](templates/indicator/fragment.html) | 指标卡片段模板 |

详细使用说明 → [config/logic/dataset.md](config/logic/dataset.md)

---

## 流式输出模式

当需要流式返回图表（如被其他技能委托生成）时，使用流式模板：

| 场景 | 模板 | 说明 |
|------|------|------|
| 独立流式页面 | [templates/echarts/streaming.html](templates/echarts/streaming.html) | 完整 HTML，含 IIFE 内联脚本 |
| 嵌入片段 | [templates/echarts/streaming_fragment.html](templates/echarts/streaming_fragment.html) | 仅脚本片段，用于批量委托 |

**流式模式特征**：

- 使用 IIFE（立即执行函数）封装脚本
- 无需外部 JS 文件依赖
- 适合流式传输和嵌入其他页面
- 多图场景下 chartsConfig 数组按图顺序逐个对象字面量追加输出，不必先构建完整数组再替换占位符，确保 head/style 部分可先流出

---

## 禁止规则

1. 禁止反问用户：直接基于现有需求执行
2. 禁止使用示例数据：必须基于真实数据
3. 禁止编造数据：不得虚构任何数据内容
4. **禁止违反不变量**：无论 L1 函数调用还是 L3 手写 option，上方硬约束表的 7 条不变量必须成立
5. **禁止 LLM 自行执行任何算术运算或单位换算**：需要计算时用 Python 或查询工具计算
6. **禁止在用户未明确要求代码块形式时输出代码块**：默认必须落盘为 .html 文件；用户明确要求代码块时禁止调用 Write 工具落盘

**L3 场景特别说明**：custom/tree/sankey/wordcloud/liquidfill 等特殊图表允许手写 series 和完整 option（参考 [references/recipes/](references/recipes/)），但必须遵守不变量——系列色走 11 色板、数值用 formatUnified、数据来自用户。

**无数据时回复**：根据您的需求，没有相关数据可以生成可视化图表。
