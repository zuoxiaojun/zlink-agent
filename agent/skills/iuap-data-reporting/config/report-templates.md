# 报告布局模板

本文件定义报告章节的布局变体，主题配置见 [config/theme.json](theme.json)。

---

## ⚠️ 重要委托声明

**所有图表和指标卡均由 `iuap-data-visualizing` 技能生成**。

- 图表样式：参考 `../iuap-data-visualizing/templates/echarts/base.html`
- 指标卡样式：参考 `../iuap-data-visualizing/templates/indicator/card.html`
- 颜色规范：参考 `../iuap-data-visualizing/config/colors.json`

本文件仅定义**章节布局结构**和**洞察文字样式**，禁止自行定义图表或指标卡的 CSS。

---

## 报告头部变体

### 标准渐变样式（默认）

```html
<div class="yonbi-rep-header">
  <h1>{{报告标题}}</h1>
  <div class="yonbi-rep-meta">分析周期：{{开始日期}} ~ {{结束日期}} | 生成时间：{{生成日期}}</div>
  <div class="yonbi-rep-summary">
    <span class="yonbi-rep-tag yonbi-rep-tag--opportunity">摘要</span>
    {{摘要内容}}
  </div>
</div>
```

### 简洁线条样式

```html
<div class="yonbi-rep-header yonbi-rep-header--simple">
  <h1>{{报告标题}}</h1>
  <div class="yonbi-rep-meta">{{元信息}}</div>
  <div class="yonbi-rep-summary">
    <span class="yonbi-rep-tag yonbi-rep-tag--opportunity">摘要</span>
    {{摘要内容}}
  </div>
</div>
```

### 带品牌色条样式

```html
<div class="yonbi-rep-header" style="position: relative; padding-top: 0;">
  <div style="height: 4px; background: linear-gradient(90deg, var(--yonbi-vis-color-primary), var(--yonbi-vis-color-secondary), var(--yonbi-vis-color-accent));"></div>
  <div style="padding: 32px 40px;">
    <h1>{{报告标题}}</h1>
    <div class="yonbi-rep-meta">{{元信息}}</div>
    <div class="yonbi-rep-summary">
      <span class="yonbi-rep-tag yonbi-rep-tag--opportunity">摘要</span>
      {{摘要内容}}
    </div>
  </div>
</div>
```

---

## 核心指标区域（必须委托给 iuap-data-visualizing）

**【重要】指标卡由 iuap-data-visualizing 统一生成，本模板不定义样式。**

### 标准嵌入方式

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">核心指标总览</div>
  <div class="yonbi-vis-cards">
    <!-- 由 iuap-data-visualizing 生成的 HTML 片段嵌入此处 -->
    {{INDICATOR_CARDS_HTML}}
  </div>
</div>
```

### 调用参数

```json
{
  "mode": "fragment",
  "CARD_TITLE": "核心指标总览",
  "CARD_LIST": [
    {
      "cardClass": "yonbi-vis-card--amount",
      "iconBgClass": "yonbi-vis-icon--amount",
      "iconClass": "fa-chart-line",
      "title": "销售金额",
      "value": "¥63.70万",
      "hasTrend": true,
      "yoy": { "label": "同比", "value": "23.68%", "trendUp": true },
      "mom": { "label": "环比", "value": "10%", "trendDown": true }
    }
  ]
}
```

### 指标类型与样式映射

> **详细规则见 iuap-data-visualizing**：[../iuap-data-visualizing/references/indicator_types.md](../iuap-data-visualizing/references/indicator_types.md)

**详细配置**：`../iuap-data-visualizing/config/indicator_mapping.json`

---

## 图文混排布局

### 上文下图（默认）

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">章节标题</div>
  <div class="yonbi-rep-insight">分析文字（先给结论）</div>
  <div class="yonbi-rep-chart" id="chart1"></div>
  <div class="yonbi-rep-insight" style="font-size: 13px; color: var(--yonbi-vis-text-muted);">图表解读</div>
</div>
```

### 上图下文

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">章节标题</div>
  <div class="yonbi-rep-chart" id="chart1"></div>
  <div class="yonbi-rep-insight">图表分析与解读</div>
</div>
```

### 左图右文

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

### 双图对比

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">章节标题</div>
  <div class="yonbi-rep-insight">对比分析说明</div>
  <div class="yonbi-rep-chart-grid">
    <div>
      <div style="font-size: 13px; color: var(--yonbi-vis-text-muted); text-align: center; margin-bottom: 8px;">图表A</div>
      <div class="yonbi-rep-chart" id="chart2a"></div>
    </div>
    <div>
      <div style="font-size:13px; color: var(--yonbi-vis-text-muted); text-align: center; margin-bottom: 8px;">图表B</div>
      <div class="yonbi-rep-chart" id="chart2b"></div>
    </div>
  </div>
  <div class="yonbi-rep-insight">对比结论</div>
</div>
```

### 表格 + 图表

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">章节标题</div>
  <div style="display: flex; gap: 24px; align-items: flex-start;">
    <div style="flex: 1; overflow-x: auto;">
      <table class="yonbi-rep-table">
        <thead><tr><th>列1</th><th>列2</th></tr></thead>
        <tbody><tr><td>值1</td><td>值2</td></tr></tbody>
      </table>
    </div>
    <div style="flex: 1;">
      <div class="yonbi-rep-chart" id="chart3" style="height: 300px;"></div>
    </div>
  </div>
</div>
```

---

## 章节模板

### 数据概览与质量

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">数据概览与质量</div>
  <div class="yonbi-rep-insight">
    <strong>数据规模：</strong>共 12,345 行，15 列<br>
    <strong>时间跨度：</strong>2024-01 至 2024-12
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
    <!-- 更多质量项 -->
  </div>
</div>
```

### 分析框架（假设树）

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">分析框架</div>
  <div class="yonbi-rep-hypothesis">
    <div class="yonbi-rep-hypothesis-item">核心问题：为什么营收下降？</div>
    <div class="yonbi-rep-hypothesis-item" style="padding-left: 20px;">
      ├── 量的问题
      <div style="padding-left: 20px;">
        │   ├── <span class="yonbi-rep-hypothesis-tag yonbi-rep-hypothesis-tag--p0">P0</span> 新客户减少
        │   └── <span class="yonbi-rep-hypothesis-tag yonbi-rep-hypothesis-tag--p1">P1</span> 老客户流失
      </div>
    </div>
  </div>
</div>
```

### 行动建议

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">行动建议</div>
  <div class="yonbi-rep-action">
    <div class="yonbi-rep-action__title"><span class="yonbi-rep-action__priority yonbi-rep-action__priority--high">高优</span> 建议标题</div>
    <div class="yonbi-rep-action__desc">具体可执行的行动描述...</div>
  </div>
  <div class="yonbi-rep-action">
    <div class="yonbi-rep-action__title"><span class="yonbi-rep-action__priority yonbi-rep-action__priority--medium">中优</span> 建议标题</div>
    <div class="yonbi-rep-action__desc">具体描述...</div>
  </div>
</div>
```

### 分析局限

```html
<div class="yonbi-rep-section">
  <div class="yonbi-rep-section__title">分析局限</div>
  <div class="yonbi-rep-insight">
    <strong>数据缺口：</strong>缺少竞品数据<br>
    <strong>因果推断：</strong>部分结论基于相关性，需进一步验证
  </div>
</div>
```
