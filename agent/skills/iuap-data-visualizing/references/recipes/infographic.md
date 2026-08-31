# 信息图（AntV Infographic）

> 展示信息图、流程图、组织架构图、时间线、数据故事等非统计图表

**实现方式**：使用 AntV Infographic 库，声明式语法，200+ 内置模板。

---

## 触发条件

用户需要**信息图、流程图、组织架构图、时间线、数据故事**等非统计图表。

**识别词**：信息图、infographic、流程图、步骤图、时间线、组织架构、数据故事

> **与 ECharts 分界**："信息展示/故事叙述" → 信息图；"数据分析/统计探索" → ECharts。

---

## CDN 地址

**主地址**：

```
https://cdn.jsdelivr.net/npm/@antv/infographic@0.2.16/dist/infographic.min.js
```

**备用地址**：

```
https://registry.npmmirror.com/@antv/infographic/0.2.16/files/dist/infographic.min.js
```

---

## 声明式语法（DSL）

### 正确格式

```
infographic 模板名称
data
  lists
    - label 标签文本
      desc 描述文本
```

**关键规则**：

- 模板名称**直接写**，不需要尖括号或引号
- 数据字段统一用 `lists`（复数）
- **严格 2 空格缩进**，禁止使用 Tab
- `label` 和 `desc` 后直接写纯文本内容

### ❌ 错误示例 vs ✅ 正确示例

| 错误写法 | 正确写法 | 问题说明 |
| --------- | --------- | --------- |
| `infographic <list-grid-compact-card>` | `infographic list-grid-compact-card` | 模板名不需要尖括号 |
| `desc <span style="color:red">文本</span>` | `desc 纯文本内容` | desc 禁止 HTML 标签 |
| `desc 🔥 热门产品` | `desc 热门产品` | desc 禁止 emoji |
| `label 🥇 第一名` | `label 第一名` | label 禁止 emoji |
| 使用 Tab 缩进 | 使用 2 空格缩进 | 缩进必须统一 |

---

## 禁止规则（强制）

| 规则 | 说明 | 原因 |
| ------ | ------ | ------ |
| **禁止 HTML 标签** | `label` 和 `desc` 字段只能包含纯文本 | DSL 解析器不支持 HTML |
| **禁止 emoji** | `label` 和 `desc` 禁止使用 emoji | 可能导致渲染异常或解析失败 |
| **禁止尖括号包裹模板名** | 模板名直接写，如 `list-grid-compact-card` | 尖括号不是语法的一部分 |
| **禁止 Tab 缩进** | 必须使用 2 空格 | DSL 解析器对缩进敏感 |

---

## 模板选择

| 用户意图 | 推荐模板 |
| --------- | --------- |
| 流程/步骤 | `list-row-simple-horizontal-arrow`、`list-column-simple-vertical-arrow` |
| 对比/差异 | `compare-binary-horizontal-compact-card-arrow`、`compare-binary-horizontal-badge-card-vs` |
| 组织/层级 | `hierarchy-mindmap-branch-gradient-compact-card` |
| 列表/排名 | `list-grid-badge-card`、`list-grid-ribbon-card` |
| 网格/卡片 | `list-grid-compact-card`、`list-grid-progress-card` |
| 柱状/进度 | `list-row-circular-progress`、`list-grid-circular-progress` |
| 金字塔 | `list-pyramid`、`list-pyramid-badge-card` |
| 瀑布流 | `list-waterfall`、`list-waterfall-badge-card` |

---

## HTML 模板

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>信息图</title>
  <script src="https://cdn.jsdelivr.net/npm/@antv/infographic@0.2.16/dist/infographic.min.js"></script>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #f5f7fa;
      display: flex; flex-direction: column; align-items: center;
      padding: 24px; min-height: 100vh;
    }
    h1 { font-size: 18px; font-weight: 500; color: #333; margin-bottom: 16px; }
    #container {
      width: 100%; max-width: 900px; height: 500px;
      background: #fff; border-radius: 12px;
      box-shadow: 0 1px 8px rgba(0,0,0,0.08); overflow: hidden;
    }
    .error-message {
      display: flex; align-items: center; justify-content: center;
      height: 100%; color: #8c8c8c; font-size: 14px;
    }
  </style>
</head>
<body>
  <h1>信息图标题</h1>
  <div id="container">
    <div class="error-message">信息图渲染中...</div>
  </div>
  <script>
    // 错误处理：检测库是否加载成功
    if (typeof AntVInfographic === 'undefined' || typeof AntVInfographic.Infographic === 'undefined') {
      document.getElementById('container').innerHTML = '<div class="error-message">信息图库加载失败，请检查网络连接后刷新页面</div>';
    } else {
      const infographic = new AntVInfographic.Infographic({
        container: '#container',
        width: '100%',
        height: '100%',
        editable: true,
      });
      infographic.render(`
infographic list-grid-compact-card
data
  lists
    - label 标签内容
      desc 描述内容
      `);
    }
  </script>
</body>
</html>
```

---

## 完整示例

### 输入数据

```
总收入：1,574.01 亿元
销售数量：10,812 件
组织覆盖：55 个
省份覆盖：24 个
```

### 正确 DSL 写法

```
infographic list-grid-compact-card
data
  lists
    - label 总收入
      desc 1,574.01 亿元
    - label 销售数量
      desc 10,812 件
    - label 组织覆盖
      desc 55 个
    - label 省份覆盖
      desc 24 个
```

---

## 质量检查清单

- [ ] 模板名称直接写，无尖括号，如 `list-grid-compact-card`
- [ ] 数据字段使用 `lists`（复数）
- [ ] 严格 2 空格缩进，无 Tab
- [ ] `label` 和 `desc` 字段为纯文本，无 HTML 标签
- [ ] `label` 和 `desc` 无 emoji
- [ ] HTML 中有库加载失败检测
