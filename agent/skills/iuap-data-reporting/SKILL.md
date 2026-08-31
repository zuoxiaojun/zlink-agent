---
name: iuap-data-reporting
description: >-
  图文报告生成技能。基于数据生成包含文字分析与图表的完整 HTML 报告，支持从轻量日常通报到深度洞察的各类报告场景。
  当用户需要生成任何形式的图文报告时使用，包括但不限于：经营分析报告、数据分析报告、周报/月报/季报/年报、专项报告、行业报告、业务报告、洞察报告、复盘报告、调研报告、数据概览报告、对比分析报告、漏斗分析报告，或需要对数据进行深度洞察、多维度分析、归因分析、趋势预测时使用。
  报告深度自适应：简单通报走轻量结构，复杂问题走 7 阶段洞察流水线。
  不适用于仅需要简单数据摘要或单独图表的场景。
metadata:
  yonbip:
    version: 15.14.4
---

# 洞察分析与报告生成技能

**定位**：给我数据，我给你一份图文并茂的分析报告。

**核心委托**：所有可视化工作（图表、指标卡）必须全权委托给 `iuap-data-visualizing` 技能，本技能专注分析逻辑和报告组装，禁止自行生成可视化图表。

---

## 硬约束

| 规则 | 说明 |
| ------ | ------ |
| **单产物输出** | **默认产物为 .html 文件并回传路径；仅当用户明确要求代码块形式时，才以单个 ```html 代码块输出，此时禁止调用 Write 工具落盘** |
| **数据真实性** | 所有分析结论必须基于真实数据，绝不杜撰 |
| **图文混排** | 报告必须同时包含文字分析段落和数据图表 |
| **批量委托** | 图表通过 requests 数组批量获取，减少调用次数 |
| **流式输出** | 报告采用流式格式，每个图表容器与内联脚本紧邻，实现渐进式渲染 |
| **主题统一** | 使用可视化技能的主题 CDN 和 11 色系列，禁止自定义 |

---

## 图表配置约束（强制）

**详细规则** → [config/chart-constraints.md](config/chart-constraints.md)

包含：常见错误对照表、响应式 Grid（强制）、图表配置铁律、容器规范

---

## 核心流程

```
步骤1：读取模板文件（必须）
├── [templates/report/base.html](templates/report/base.html) → HTML 外壳
├── [templates/report/sections.md](templates/report/sections.md) → 章节片段库
└── [fragment.html](../iuap-data-visualizing/templates/indicator/fragment.html) → 指标卡结构

步骤2：意图识别与数据获取
├── 意图识别 → [reference/mode-selection.md](reference/mode-selection.md)
└── 数据获取（以用户意图为准，无固定优先级顺序）：上下文 → 文件 → 查询 → 提醒

【判断】数据是否满足分析/图表需求？
├── 满足 → 直接使用
└── 不足（缺少计算字段）→ 用 Python 或查询工具计算，禁止自行执行任何算术运算或单位换算

步骤3：分析执行与图表需求收集
├── 自主模式 → 7阶段流水线（见 insight-framework.md）
├── 用户驱动模式 → 按用户规划执行
└── 构建 requests 数组

步骤4：批量委托可视化技能
├── 委托协议 → [config/delegation.md](config/delegation.md)
└── requests 数组批量提交

步骤5：流式组装报告
├── 每章节：标题 → 分析文字 → 图表容器 → 内联脚本 → 立即渲染
└── 按硬约束表·单产物输出规则执行（默认 .html 文件，head/style 部分先组装、章节内容逐段追加；用户明确要求代码块时输出代码块）

步骤6：输出校验
├── 产物是 HTML，不是 JSON
├── 按硬约束表·单产物输出规则执行（默认 .html 文件；用户明确要求代码块时输出代码块）
└── 所有章节已内嵌
```

**流式输出顺序**：

```
报告头部 → 章节1(标题→文字→容器→脚本→渲染) → 章节2(...) → ... → 报告底部 → 全局脚本
```

---

## 技能依赖

| 技能名称 | 依赖类型 | 说明 |
| --------- | --------- | ------ |
| **iuap-data-visualizing** | **强制依赖** | 所有可视化工作全权委托 |
| iuap-data-file-io | 可选依赖 | 文件读取，失败时降级使用 Read 工具 |
| iuap-data-querying | 可选依赖 | 数据查询，无数据时调用 |

---

## 规则文件索引

### 基础规则（必读）

| 文件 | 内容 |
| ------ | ------ |
| [config/delegation.md](config/delegation.md) | 委托协议：请求项结构、字段说明、示例 |
| [config/chart-constraints.md](config/chart-constraints.md) | 图表配置约束：图例、标题、容器规范 |
| [config/batch_delegation.json](config/batch_delegation.json) | 批量委托配置 |
| [config/report-styles.css](config/report-styles.css) | 报告样式真理源 |

### 方法论规则（按需加载）

| 文件 | 内容 |
| ------ | ------ |
| [reference/mode-selection.md](reference/mode-selection.md) | 意图识别与模式选择 |
| [reference/dimension-selection.md](reference/dimension-selection.md) | 动态分析维度选择 |
| [reference/methodology/insight-framework.md](reference/methodology/insight-framework.md) | 7阶段分析流水线 |
| [reference/methodology/statistical-validation.md](reference/methodology/statistical-validation.md) | 统计验证方法 |
| [reference/methodology/business-models.md](reference/methodology/business-models.md) | 商业模型参考 |

### 可视化技能引用

| 文件 | 内容 |
| ------ | ------ |
| [layout/base.md](../iuap-data-visualizing/config/layout/base.md) | 布局规则：标题、图例、grid、容器 |
| [logic/base.md](../iuap-data-visualizing/config/logic/base.md) | 逻辑规则：数值格式化 |
| [logic/dataset.md](../iuap-data-visualizing/config/logic/dataset.md) | dataset 模式规则 |
| [colors/series.md](../iuap-data-visualizing/config/colors/series.md) | 11 色系列 |
| [indicator_mapping.md](../iuap-data-visualizing/config/indicator_mapping.md) | 指标类型识别规则 |

---

## 报告结构规划

| 报告类型 | 推荐章节 |
| ---------- | ---------- |
| 经营分析报告 | KPI总览 → 趋势分析 → 结构拆解 → 异常诊断 → 行动建议 |
| 专题分析报告 | 问题定义 → 数据探索 → 原因分析 → 结论与建议 |
| 数据概览报告 | 核心指标 → 分布概况 → 排名 → 关键发现 |
| 对比分析报告 | 对比维度选择 → 差异量化 → 原因分析 → 改进建议 |

**完整章节片段库** → [templates/report/sections.md](templates/report/sections.md)

---

## 无数据处理

无数据时回复：

> 根据您的需求，没有相关数据可以生成报告。

---

## 禁止规则

1. 禁止指定具体图表类型（如 "line"、"pie"）
2. 禁止定义图表样式
3. 禁止自定义主题或颜色
4. 禁止覆盖可视化技能的选型决策
5. 禁止自行编写 legend / title 配置
6. 禁止生成空容器（无 loading 占位符）
7. 禁止自行编写图表脚本：所有图表脚本必须来自可视化技能返回，报告技能只负责嵌入
8. 禁止 LLM 自行执行任何算术运算或单位换算：需要计算时用 Python 或查询工具计算，数值引用规范详见 [logic/base.md](../iuap-data-visualizing/config/logic/base.md)
9. 禁止模糊引用数值：文字中数值必须与数据源一致，禁止"约""近"等模糊表述
10. **禁止在用户未明确要求代码块形式时输出代码块**：默认必须落盘为 .html 文件；用户明确要求代码块时禁止调用 Write 工具落盘

---

## 质量检查清单

### 输出完整性

- [ ] 仅输出一个产物（默认 .html 文件；用户明确要求时代码块）
- [ ] 所有章节在同一产物中
- [ ] 所有图表、指标卡已内嵌

### 委托规范

- [ ] 使用 requests 数组批量委托
- [ ] 未指定图表类型，只传递分析目的
- [ ] 使用可视化技能的主题 CDN 和 11 色系列

### 脚本质量

- [ ] 图表 option 配置无语法错误（括号闭合、属性键唯一）
- [ ] 报告内所有 JS 脚本无语法错误
- [ ] HTML 标签正确闭合
- [ ] 图表必须来自可视化技能返回，禁止自行编写图表脚本
- [ ] 原样嵌入可视化技能返回的图表片段

### 数据与内容

- [ ] 数据来源已验证
- [ ] 文字中数值与数据源一致，需要计算时用 Python 或查询工具计算
- [ ] 单位换算正确，无重复追加单位
- [ ] 摘要 ≤ 5 句话
- [ ] 每章节有"分析文字 + 图表"

---

## 参考文件导航

| 文件 | 何时查阅 |
| ------ | ---------- |
| [templates/report/sections.md](templates/report/sections.md) | 章节片段库，生成报告时必须查阅 |
| [templates/report/base.html](templates/report/base.html) | 报告模板 |
| [config/report-styles.css](config/report-styles.css) | 报告样式真理源 |
| [config/report-types.json](config/report-types.json) | 规划报告结构时 |

**样式 CDN**：<https://cdn.jsdelivr.net/gh/liuqxuan/BI-DefaultTheme@v1.0.11/report-styles.css>

**主题 CDN**：<https://cdn.jsdelivr.net/gh/liuqxuan/BI-DefaultTheme@v1.0.12/registe-theme.js>
