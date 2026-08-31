# 报告章节片段库

本文档提供可组合的章节 HTML 片段，根据报告需求灵活选用。

---

## ⚠️ 核心原则

### 灵活性优先

- 章节片段**可选可组合**，非强制固定结构
- 根据实际分析需求选择合适的片段
- 可自定义章节顺序和数量

### 样式来源（二选一，互斥规则）

**样式真理源（本地）**：[config/report-styles.css](../../config/report-styles.css)

技能执行时必须读取此文件获取样式内容。

**样式加载策略**：
**⚠️  铁律：只能选择一种样式策略，禁止同时存在！**

| 策略 | 说明 |
|------|------|
| 优先远程加载 | 报告通过 `<link>` 引用 CDN（默认） |
| 降级机制 | CDN 不可用时，内嵌本地样式到 `<style>` 标签 |

**样式 CDN**：<https://cdn.jsdelivr.net/gh/liuqxuan/BI-DefaultTheme@v1.0.11/report-styles.css>

**互斥检查**：

- 如果输出包含 `<link rel="stylesheet"` → 必须删除所有 `<style>` 标签
- 如果输出包含 `<style>` 标签 → 必须删除所有 `<link rel="stylesheet"`

### 可视化委托原则

- **图表类型**：由 iuap-data-visualizing 根据数据特征智能选择
- **指标卡结构**：使用 fragment.html HTML 结构
- **主题和颜色**：必须使用可视化技能的配置
- **批量委托**：报告技能使用 requests 数组一次性提交所有请求

---

## 批量委托示例

### 完整批量委托请求

```json
{
  "skill": "iuap-data-visualizing",
  "requests": [
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
            "value": "¥63.70万",
            "hasTrend": true,
            "yoy": {"label": "同比", "value": "23.68%", "trendUp": true}
          },
          {
            "cardClass": "yonbi-vis-card--volume",
            "iconBgClass": "yonbi-vis-icon--volume",
            "iconClass": "fa-boxes",
            "title": "销售数量",
            "value": "23,725"
          }
        ]
      }
    },
    {
      "id": "chart-trend",
      "analysisPurpose": "趋势分析",
      "data": {
        "columns": ["月份", "销售额"],
        "rows": [["2024-01", 12345], ["2024-02", 15678], ["2024-03", 18900]]
      },
      "context": {
        "title": "月度销售趋势",
        "containerId": "chart-trend"
      }
    },
    {
      "id": "chart-composition",
      "analysisPurpose": "占比构成",
      "data": {
        "columns": ["品类", "销售金额"],
        "rows": [["电子产品", 320000], ["日用品", 180000], ["服装", 150000]]
      },
      "context": {
        "title": "品类销售占比",
        "containerId": "chart-composition"
      }
    }
  ]
}
```

### 批量委托性能优势

| 指标 | 逐个委托 | 批量委托 | 提升 |
|------|----------|----------|------|
| 委托次数 | N次 | 1次 | ↓ (N-1)次 |
| 文件读取 | N×5次 | 5次 | ↓ (N-1)×5次 |

---

## ⚠️⚠️⚠️ 指标卡类名警告

> **问题已多次出现**：使用错误的类名会导致样式完全错误！

### 类名对照表

| 必须使用 ✅ | 禁止使用 ❌ | 说明 |
| ------------ | ------------ | ------ |
| `.yonbi-vis-cards` | `.data-cards` | 容器类名 |
| `.yonbi-vis-card__title` | `.label` | 标题类名 |
| `.yonbi-vis-card__value` | `.value` | 数值类名 |
| 直接写入数值 | `<span class="unit">` | 单位处理 |
| `.yonbi-vis-trend` > `.yonbi-vis-trend__item` | `.trend`（单层） | 趋势结构 |

### 样式来源

**样式真理源（本地）**：[config/report-styles.css](../../config/report-styles.css)

技能执行时必须读取此文件，样式内容与远程 CDN 完全一致。

**样式加载策略**：

| 策略 | 说明 |
|------|------|
| 优先远程加载 | 报告通过 `<link>` 引用 CDN |
| 降级机制 | CDN 不可用时，内嵌本地样式到 `<style>` 标签 |

**样式 CDN**：<https://cdn.jsdelivr.net/gh/liuqxuan/BI-DefaultTheme@v1.0.11/report-styles.css>

**HTML 结构**：../iuap-data-visualizing/templates/indicator/fragment.html

---

## 片段一：核心指标总览

**用途**：展示关键 KPI 指标卡片

**分析目的**：指标卡

**批量委托请求项**：

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
        "value": "¥63.70万",
        "hasTrend": true,
        "yoy": {"label": "同比", "value": "23.68%", "trendUp": true}
      }
    ]
  }
}
```

> **注意**：此请求项需与其他图表请求项合并为 `requests` 数组一次性提交。详见上方「批量委托示例」。

**HTML 结构**：

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">核心指标总览</div>
  <div class="yonbi-vis-cards">
    <!-- 金额类型 -->
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
        <div class="yonbi-vis-trend__item">
          <span class="yonbi-vis-trend__label">环比</span>
          <span class="yonbi-vis-trend--down"><i class="fa fa-arrow-down"></i>10%</span>
        </div>
      </div>
    </div>
    <!-- 更多卡片... -->
  </div>
</div>
```

**指标类型与类名映射**：

> **详细规则见 iuap-data-visualizing**：[../iuap-data-visualizing/config/indicator_mapping.md](../iuap-data-visualizing/config/indicator_mapping.md)

**趋势样式**：

- `yonbi-vis-trend--up`：上涨（橙红色 #fb6832）
- `yonbi-vis-trend--down`：下跌（翠绿色 #1cd46b）
- `yonbi-vis-trend--neutral`：持平（灰色 #8c8c8c）
- 无趋势时删除 `<div class="yonbi-vis-trend">...</div>`

---

## 片段二：趋势分析章节

**用途**：展示时间序列数据的趋势变化

**分析目的**：趋势分析

**批量委托请求项**：

```json
{
  "id": "chart-trend",
  "analysisPurpose": "趋势分析",
  "data": {
    "columns": ["月份", "销售额"],
    "rows": [["2024-01", 12345], ["2024-02", 15678]]
  },
  "context": {
    "title": "月度销售趋势",
    "containerId": "chart-trend"
  }
}
```

**注意**：图表类型由可视化技能根据数据连续性自动选择（line/area/bar）

**HTML 结构**：

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">趋势分析 <span class="yonbi-rep-confidence yonbi-rep-confidence--high">高置信度</span></div>
  <div class="yonbi-rep-insight">
    <!-- 发现：陈述数据事实 -->
    2025年Q1总营收达 <span class="yonbi-rep-highlight">1,234万元</span>，
    同比增长 <span class="yonbi-rep-trend--up">23.5%</span>。

    <!-- 解读：解释为什么 -->
    <span class="yonbi-rep-tag yonbi-rep-tag--opportunity">机会点</span>
    增长主要受3月份大促拉动，新品类贡献了增量的42%，
    成本占比下降 <span class="yonbi-rep-trend--down">5个百分点</span>。

    <!-- 意义：指向行动 -->
    建议加大该品类推广预算，Q2复制大促运营策略。
  </div>
  <!-- 图表容器：类型由可视化技能自动选择 -->
  <div class="yonbi-rep-chart" id="chart-trend"></div>
</div>
```

---

## 片段三：结构分析章节

**用途**：展示分类数据的占比分布

**分析目的**：占比构成

**批量委托请求项**：

```json
{
  "id": "chart-composition",
  "analysisPurpose": "占比构成",
  "data": {
    "columns": ["品类", "销售金额"],
    "rows": [["电子产品", 320000], ["日用品", 180000], ["服装", 150000]]
  },
  "context": {
    "title": "品类销售占比",
    "containerId": "chart-composition"
  }
}
```

**注意**：图表类型由可视化技能根据分类数量自动选择（pie/donut/treemap/sunburst）

**HTML 结构**：

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">结构分析</div>
  <div class="yonbi-rep-insight">
    Top 3 品类贡献了 <span class="yonbi-rep-highlight">68%</span> 的销售额，
    其中电子产品占比最高达 <span class="yonbi-rep-highlight">32%</span>。
    <span class="yonbi-rep-tag yonbi-rep-tag--finding">结构性发现</span>
    品类集中度较高，存在一定的依赖风险。
  </div>
  <div class="yonbi-rep-chart" id="chart-composition"></div>
</div>
```

---

## 片段四：归因分析章节

**用途**：展示多维度归因和贡献度

**分析目的**：归因分析（属于分类对比的变体）

**批量委托请求项**：

```json
{
  "id": "chart-attribution",
  "analysisPurpose": "分类对比",
  "data": {
    "columns": ["维度", "贡献值"],
    "rows": [["华东区域", 185000], ["华南区域", 120000], ["华北区域", 80000]]
  },
  "context": {
    "title": "归因分析",
    "containerId": "chart-attribution"
  }
}
```

**HTML 结构**：

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">归因分析</div>
  <div class="yonbi-rep-insight">
    销售增长主要来自 <span class="yonbi-rep-highlight">华东区域</span>，
    贡献了增量的 <span class="yonbi-rep-highlight">58%</span>。
    <span class="yonbi-rep-tag yonbi-rep-tag--opportunity">机会点</span>
    华东区域的大客户拓展策略效果显著。
  </div>
  <div class="yonbi-rep-chart" id="chart-attribution"></div>
  <!-- 归因贡献度表格 -->
  <table class="yonbi-rep-table">
    <thead>
      <tr><th>维度</th><th>贡献值</th><th>贡献占比</th><th>变化方向</th></tr>
    </thead>
    <tbody>
      <tr>
        <td>华东区域</td>
        <td>+¥185万</td>
        <td>
          <div class="yonbi-rep-progress">
            <div class="yonbi-rep-progress__fill--positive" style="width: 58%"></div>
            <span>58%</span>
          </div>
        </td>
        <td class="yonbi-vis-trend--up">↑</td>
      </tr>
    </tbody>
  </table>
</div>
```

---

## 片段五：对比分析章节

**用途**：展示多维度/多时期对比

**分析目的**：分类对比

**批量委托请求项**：

```json
{
  "id": "chart-comparison",
  "analysisPurpose": "分类对比",
  "data": {
    "columns": ["区域", "销售金额"],
    "rows": [["华东", 320000], ["华南", 220000], ["华北", 180000]]
  },
  "context": {
    "title": "区域销售对比",
    "containerId": "chart-comparison"
  }
}
```

**HTML 结构**：

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">对比分析</div>
  <div class="yonbi-rep-insight">
    各区域销售表现差异明显，<span class="yonbi-rep-highlight">华东区域</span>以
    <span class="yonbi-rep-highlight">¥320万</span>位居首位，
    较第二名高出 <span class="yonbi-rep-highlight">42%</span>。
  </div>
  <div class="yonbi-rep-chart" id="chart-comparison"></div>
</div>
```

---

## 片段六：异常检测章节

**用途**：展示异常数据和风险预警

**分析目的**：分布分析（带异常标注）

**批量委托请求项**：

```json
{
  "id": "chart-anomaly",
  "analysisPurpose": "分布分析",
  "data": {
    "columns": ["月份", "销售额"],
    "rows": [["2024-01", 120000], ["2024-02", 150000], ["2024-08", 65000]]
  },
  "context": {
    "title": "销售额分布与异常",
    "containerId": "chart-anomaly"
  }
}
```

**HTML 结构**：

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">异常检测</div>
  <div class="yonbi-rep-risk">
    <h3>风险提示</h3>
    <ul>
      <li><strong>断崖式下降：</strong>8月销售额环比下降 <span class="yonbi-rep-highlight">35%</span>，需重点关注</li>
      <li><strong>集中度过高：</strong>Top 1 客户贡献 45% 收入，存在依赖风险</li>
    </ul>
  </div>
  <div class="yonbi-rep-chart" id="chart-anomaly"></div>
</div>
```

---

## 片段七：数据概览与质量

**用途**：展示数据基本情况和质量评估

**HTML 结构**：

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">数据概览与质量</div>
  <div class="yonbi-rep-insight">
    <strong>数据规模：</strong>共 12,345 行，15 列，时间跨度 2024-01 至 2024-12<br>
    <strong>数据粒度：</strong>每行代表一个订单记录
  </div>
  <div class="yonbi-rep-quality">
    <div class="yonbi-rep-quality__item">
      <div class="yonbi-rep-quality__label">完整性</div>
      <div class="yonbi-rep-quality__status">✅</div>
    </div>
    <div class="yonbi-rep-quality__item">
      <div class="yonbi-rep-quality__label">准确性</div>
      <div class="yonbi-rep-quality__status">⚠️</div>
    </div>
    <div class="yonbi-rep-quality__item">
      <div class="yonbi-rep-quality__label">一致性</div>
      <div class="yonbi-rep-quality__status">✅</div>
    </div>
    <div class="yonbi-rep-quality__item">
      <div class="yonbi-rep-quality__label">时效性</div>
      <div class="yonbi-rep-quality__status">✅</div>
    </div>
    <div class="yonbi-rep-quality__item">
      <div class="yonbi-rep-quality__label">唯一性</div>
      <div class="yonbi-rep-quality__status">✅</div>
    </div>
  </div>
</div>
```

---

## 片段八：分析框架（MECE假设树）

**用途**：展示问题拆解和分析思路

**HTML 结构**：

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">分析框架</div>
  <div class="yonbi-rep-hypothesis">
    <div class="yonbi-rep-hypothesis-item">
      核心问题：为什么营收下降？
    </div>
    <div class="yonbi-rep-hypothesis-item" style="padding-left: 20px;">
      ├── 量的问题（客户数 × 购买频次）
      <div style="padding-left: 20px;">
        │   ├── <span class="yonbi-rep-hypothesis-tag yonbi-rep-hypothesis-tag--p0">P0</span> 新客户减少 → 获客渠道效率下降
        │   ├── <span class="yonbi-rep-hypothesis-tag yonbi-rep-hypothesis-tag--p0">P0</span> 老客户流失 → 产品体验/竞品替代
        │   └── <span class="yonbi-rep-hypothesis-tag yonbi-rep-hypothesis-tag--p1">P1</span> 购买频次降低 → 消费力下降
      </div>
    </div>
    <div class="yonbi-rep-hypothesis-item" style="padding-left: 20px;">
      ├── 价的问题（客单价 × 折扣率）
      <div style="padding-left: 20px;">
        │   ├── <span class="yonbi-rep-hypothesis-tag yonbi-rep-hypothesis-tag--p1">P1</span> 客单价下降 → 产品结构下移
        │   └── <span class="yonbi-rep-hypothesis-tag yonbi-rep-hypothesis-tag--p2">P2</span> 折扣率上升 → 促销依赖
      </div>
    </div>
  </div>
</div>
```

---

## 片段九：行动建议

**用途**：给出可执行的建议

**分析目的**：文字卡片，无需图表

**HTML 结构**：

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">行动建议</div>
  <div class="yonbi-rep-action">
    <div class="yonbi-rep-action__title"><span class="yonbi-rep-action__priority yonbi-rep-action__priority--high">高优</span> 启动大客户挽回计划</div>
    <div class="yonbi-rep-action__desc">针对流失风险前10名客户，由销售总监亲自跟进，预计挽回 ¥50万/月</div>
  </div>
  <div class="yonbi-rep-action">
    <div class="yonbi-rep-action__title"><span class="yonbi-rep-action__priority yonbi-rep-action__priority--medium">中优</span> 优化获客渠道</div>
    <div class="yonbi-rep-action__desc">将预算向转化率最高的2个渠道倾斜，预计提升获客效率 20%</div>
  </div>
  <div class="yonbi-rep-action">
    <div class="yonbi-rep-action__title"><span class="yonbi-rep-action__priority yonbi-rep-action__priority--low">低优</span> 产品结构优化</div>
    <div class="yonbi-rep-action__desc">逐步提升高毛利产品占比，预计Q2提升 5 个百分点</div>
  </div>
</div>
```

---

## 片段十：分析局限

**用途**：说明分析的局限性和数据缺口

**HTML 结构**：

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">分析局限</div>
  <div class="yonbi-rep-insight">
    <strong>数据缺口：</strong>缺少竞争对手数据，无法进行市场份额分析<br>
    <strong>时间限制：</strong>仅分析近12个月数据，长期趋势可能存在偏差<br>
    <strong>因果推断：</strong>部分结论基于相关性，因果关系需进一步验证
  </div>
</div>
```

---

## 图文布局变体

### 模式一：上文下图（默认）

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">章节标题</div>
  <div class="yonbi-rep-insight">分析文字（先给结论）</div>
  <div class="yonbi-rep-chart" id="chart1"></div>
  <div class="yonbi-rep-insight" style="font-size: 13px; color: var(--yonbi-vis-text-muted);">图表解读</div>
</div>
```

### 模式二：上图下文

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">章节标题</div>
  <div class="yonbi-rep-chart" id="chart1"></div>
  <div class="yonbi-rep-insight">图表分析与解读</div>
</div>
```

### 模式三：左图右文

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">章节标题</div>
  <div style="display: flex; gap: 24px; align-items: flex-start;">
    <div class="yonbi-rep-chart" id="chart1" style="flex: 3; height: 350px;"></div>
    <div style="flex: 2;">
      <div class="yonbi-rep-insight">分析与解读</div>
    </div>
  </div>
</div>
```

### 模式四：双图对比

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">章节标题</div>
  <div class="yonbi-rep-insight">对比分析说明</div>
  <div class="yonbi-rep-chart-grid">
    <div>
      <div style="font-size: 13px; color: var(--yonbi-vis-text-muted); text-align: center; margin-bottom: 8px;">图表A标题</div>
      <div class="yonbi-rep-chart" id="chart2a"></div>
    </div>
    <div>
      <div style="font-size: 13px; color: var(--yonbi-vis-text-muted); text-align: center; margin-bottom: 8px;">图表B标题</div>
      <div class="yonbi-rep-chart" id="chart2b"></div>
    </div>
  </div>
  <div class="yonbi-rep-insight">对比结论</div>
</div>
```

### 模式五：表格 + 图表

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">章节标题</div>
  <div style="display: flex; gap: 24px; align-items: flex-start;">
    <div style="flex: 1; overflow-x: auto;">
      <table class="yonbi-rep-table">
        <thead><tr><th>列1</th><th>列2</th><th>列3</th></tr></thead>
        <tbody><tr><td>值1</td><td>值2</td><td>值3</td></tr></tbody>
      </table>
    </div>
    <div style="flex: 1;">
      <div class="yonbi-rep-chart" id="chart3" style="height: 300px;"></div>
    </div>
  </div>
  <div class="yonbi-rep-insight">分析解读</div>
</div>
```

---

## 底部标签

```html
<div class="yonbi-rep-footer">
  <div class="yonbi-rep-footer__tags">
    <span class="yonbi-rep-footer__tag yonbi-rep-footer__tag--source"><i class="fa fa-database"></i>数据来源：{{DATA_SOURCE}}</span>
    <span class="yonbi-rep-footer__tag yonbi-rep-footer__tag--method"><i class="fa fa-chart-line"></i>分析方法：{{ANALYSIS_METHODS}}</span>
  </div>
</div>
```

**标签类型**：

| 类型 | 类名 | 颜色 |
|------|------|------|
| 数据来源 | yonbi-rep-footer__tag--source | 主蓝 #3293fb |
| 分析方法 | yonbi-rep-footer__tag--method | 亮绿 #6bbd2e |

---

## 图表脚本示例（强制）

**每个图表必须使用响应式 grid**：

```html
<div class="yonbi-rep-chart" id="chart-trend">
  <div class="yonbi-rep-loading">图表渲染中...</div>
</div>
<script>
(function() {
  if (typeof echarts === 'undefined') return;
  var container = document.getElementById('chart-trend');
  if (!container) return;
  var chart = echarts.init(container, 'defaultTheme');
  chart.setOption({
    title: { text: '月度销售趋势', left: 16, top: 8, textStyle: { fontSize: 14, fontWeight: 600, color: '#374151' } },
    tooltip: { trigger: 'axis' },
    legend: { bottom: 8, left: 'center', itemWidth: 12, itemHeight: 12 },
    dataset: { source: [['月份', '销售额'], ['2024-01', 12345], ['2024-02', 15678]] },
    grid: getResponsiveGrid(container),  // ← 使用响应式 grid
    xAxis: { type: 'category' },
    yAxis: { type: 'value', nameTextStyle: { color: '#666666', fontSize: 12 } },
    series: [{ type: 'bar', barCategoryGap: '70%', itemStyle: { barBorderRadius: [3, 3, 0, 0] } }]
  });
  if (!window.__charts) window.__charts = [];
  window.__charts.push(chart);
})();
</script>
```

**关键点**：

- `grid: getResponsiveGrid(container)` 必须调用，禁止使用固定值
- 函数定义在 `<head>` 中，所有图表共用

---

## 洞察文字撰写规范

遵循 **"发现→解读→意义"三段式**：

```html
<div class="yonbi-rep-insight">
  <!-- 发现：陈述数据事实 -->
  2025年Q1总营收达 <span class="yonbi-rep-highlight">1,234万元</span>，
  同比增长 <span class="yonbi-rep-trend--up">23.5%</span>。

  <!-- 解读：解释为什么 -->
  <span class="yonbi-rep-tag yonbi-rep-tag--opportunity">机会点</span>
  增长主要受3月份大促拉动，新品类贡献了增量的42%，
  成本占比下降 <span class="yonbi-rep-trend--down">5个百分点</span>。

  <!-- 意义：指向行动 -->
  建议加大该品类推广预算，Q2复制大促运营策略。
</div>
```

### 趋势数字样式规则

在洞察文字中，涉及趋势变化的数字必须使用对应的样式：

| 趋势方向 | 样式类名 | 颜色 | 触发词示例 |
|----------|----------|------|------------|
| 上涨/增长/提升/增加 | `<span class="yonbi-rep-trend--up">` | 橙红 #fb6832 | 增长23.5%、提升10个百分点、同比+15% |
| 下跌/下降/减少/降低 | `<span class="yonbi-rep-trend--down">` | 翠绿 #1cd46b | 下降12%、减少5万、环比-8% |

**判断规则**：

1. 识别数字前的动词/形容词：增长、上升、提高 → yonbi-rep-trend--up；下降、减少、降低 → yonbi-rep-trend--down
2. 识别数字符号：+、↑ → yonbi-rep-trend--up；-、↓ → yonbi-rep-trend--down
3. 仅包裹表示变化幅度的数字，不包裹绝对值数字（绝对值用 `yonbi-rep-highlight`）

### 洞察标注类型

| 类型 | 类名 | 适用场景 |
| ------ | ------ | ---------- |
| 风险预警 | `.yonbi-rep-tag--risk` | 需要立即关注的负面信号 |
| 机会点 | `.yonbi-rep-tag--opportunity` | 可以利用的正面信号 |
| 结构性发现 | `.yonbi-rep-tag--finding` | 揭示底层规律的发现 |
| 背景信息 | `.yonbi-rep-tag--info` | 理解数据的必要上下文 |

### 置信度标注

| 置信度 | 类名 | 含义 |
| -------- | ------ | ------ |
| 高 | `.yonbi-rep-confidence--high` | 结论可靠，可直接决策 |
| 中 | `.yonbi-rep-confidence--medium` | 结论可信但需进一步验证 |
| 低 | `.yonbi-rep-confidence--low` | 结论为推测，需谨慎使用 |
| 假设 | `.yonbi-rep-confidence--hypothesis` | 仅作为假设方向 |

---

## 章节组合示例

### 经营分析报告

```
1. 核心指标总览（片段一）
2. 趋势分析（片段二）
3. 结构分析（片段三）
4. 归因分析（片段四）
5. 异常检测（片段六，可选）
6. 行动建议（片段九）
```

### 专题分析报告

```
1. 分析框架（片段八）
2. 数据概览与质量（片段七）
3. 趋势分析（片段二）
4. 归因分析（片段四）
5. 行动建议（片段九）
6. 分析局限（片段十）
```

### 数据概览报告

```
1. 核心指标总览（片段一）
2. 数据概览与质量（片段七）
3. 结构分析（片段三）
4. 对比分析（片段五）
```
