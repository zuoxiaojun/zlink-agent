# 指标卡样式规则

---

## 类名约束（严重警告）

使用错误类名将导致样式完全错误：

| 必须使用 ✅ | 禁止使用 ❌ | 说明 |
| ------------ | ------------ | ------ |
| `.yonbi-vis-cards` | `.data-cards` | 容器类名 |
| `.yonbi-vis-card` | `.indicator-card` | 卡片类名 |
| `.yonbi-vis-icon-bg` | `.icon-wrapper` | 图标容器类名 |
| `.yonbi-vis-card__icon` | `.icon` | 图标类名 |
| `.yonbi-vis-card__title` | `.label`、`.card-title` | 标题类名 |
| `.yonbi-vis-card__value` | `.value` | 数值类名 |
| `.yonbi-vis-trend > .yonbi-vis-trend__item` | `.trend`（单层）、`.trend-item.up` | 趋势结构 |

---

## 尺寸规范

| 元素 | 尺寸 |
| ------ | ------ |
| 图标容器 | 20px × 20px |
| 图标字号 | 10px |
| 标题字号 | 15px |
| 数值字号 | 24px |
| 趋势字号 | 13px |
| 卡片最小高度 | 140px |
| 卡片内边距 | 20px 24px |

---

## 颜色规范

### 背景色（11 种类型）

| 类型 | 背景色 |
| ------ | -------- |
| amount | rgba(50, 147, 251, 0.1) |
| volume | rgba(50, 196, 250, 0.1) |
| profit | rgba(130, 223, 43, 0.1) |
| cost | rgba(252, 181, 48, 0.1) |
| sales | rgba(251, 104, 50, 0.1) |
| users | rgba(115, 124, 253, 0.1) |
| rate | rgba(28, 212, 107, 0.1) |
| time | rgba(185, 114, 252, 0.1) |
| growth | rgba(119, 216, 63, 0.1) |
| inventory | rgba(251, 163, 68, 0.1) |
| customer | rgba(246, 189, 76, 0.1) |

### 图标背景色

与类型颜色相同，使用实色：

| 类型 | 图标背景色 |
| ------ | ----------- |
| amount | #3293fb |
| volume | #32c4fa |
| profit | #82df2b |
| cost | #fcb530 |
| sales | #fb6832 |
| users | #737cfd |
| rate | #1cd46b |
| time | #b972fc |
| growth | #77d83f |
| inventory | #fba344 |
| customer | #f6bd4c |

### 趋势颜色

| 趋势 | 颜色 | 类名 |
|------|------|------|
| 上涨 | #fb6832 | `.yonbi-vis-trend--up` |
| 下跌 | #1cd46b | `.yonbi-vis-trend--down` |
| 持平 | #8c8c8c | `.yonbi-vis-trend--neutral` |

---

## HTML 结构（强制）

**必须使用以下结构，禁止自行编写：**

```html
<div class="yonbi-vis-cards">
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
</div>
```

---

## CSS 样式（完整）

```css
.yonbi-vis-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 200px), 1fr));
  gap: 16px;
  width: 100%;
  margin: 20px 0;
}

.yonbi-vis-card {
  position: relative;
  border-radius: 8px;
  opacity: 1;
  overflow: hidden;
  min-height: 140px;
  height: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
}

.yonbi-vis-card__header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.yonbi-vis-icon-bg {
  position: relative;
  width: 20px;
  height: 20px;
  border-radius: 6px;
  flex-shrink: 0;
}

.yonbi-vis-card__icon {
  position: absolute;
  left: 0;
  top: 0;
  width: 20px;
  height: 20px;
  line-height: 20px !important;
  text-align: center;
  font-size: 10px;
  color: #ffffff;
  z-index: 1;
}

.yonbi-vis-card__title {
  font-size: 15px;
  font-weight: 600;
  color: #333333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.yonbi-vis-card__value {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.3;
  color: #111827;
  margin-bottom: 8px;
  word-break: break-all;
  overflow-wrap: break-word;
}

.yonbi-vis-card__unit {
  font-size: 15px;
  font-weight: 600;
  color: #333333;
  margin-left: 2px;
}

.yonbi-vis-trend {
  display: flex;
  gap: 32px;
  margin-top: auto;
}

.yonbi-vis-trend__item {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
}

.yonbi-vis-trend__label {
  font-size: 12px;
  color: #4B5563;
  font-weight: 500;
}

.yonbi-vis-trend--up {
  font-size: 13px;
  color: #fb6832;
  font-weight: 600;
}

.yonbi-vis-trend--down {
  font-size: 13px;
  color: #1cd46b;
  font-weight: 600;
}

.yonbi-vis-trend--neutral {
  font-size: 13px;
  color: #8c8c8c;
  font-weight: 600;
}
```

---

## 类型-图标-类名映射

| 类型 | 图标 | 卡片类名 | 图标容器类名 |
| ------ | ------ | --------- | ------------- |
| amount | fa-coins | yonbi-vis-card--amount | yonbi-vis-icon--amount |
| volume | fa-boxes | yonbi-vis-card--volume | yonbi-vis-icon--volume |
| profit | fa-sack-dollar | yonbi-vis-card--profit | yonbi-vis-icon--profit |
| cost | fa-file-invoice-dollar | yonbi-vis-card--cost | yonbi-vis-icon--cost |
| sales | fa-shopping-cart | yonbi-vis-card--sales | yonbi-vis-icon--sales |
| users | fa-users | yonbi-vis-card--users | yonbi-vis-icon--users |
| rate | fa-percentage | yonbi-vis-card--rate | yonbi-vis-icon--rate |
| time | fa-clock | yonbi-vis-card--time | yonbi-vis-icon--time |
| growth | fa-chart-line | yonbi-vis-card--growth | yonbi-vis-icon--growth |
| inventory | fa-warehouse | yonbi-vis-card--inventory | yonbi-vis-icon--inventory |
| customer | fa-user-tie | yonbi-vis-card--customer | yonbi-vis-icon--customer |

---

## 常见错误示例

### 错误 1：使用错误的卡片类名

```html
<!-- ❌ 错误 -->
<div class="indicator-card yonbi-vis-card--amount">

<!-- ✅ 正确 -->
<div class="yonbi-vis-card yonbi-vis-card--amount">
```

### 错误 2：使用错误的图标容器类名

```html
<!-- ❌ 错误 -->
<div class="icon-wrapper yonbi-vis-icon--amount">

<!-- ✅ 正确 -->
<div class="yonbi-vis-icon-bg yonbi-vis-icon--amount">
```

### 错误 3：错误的趋势结构

```html
<!-- ❌ 错误：单层结构 -->
<span class="trend-item up"><i class="fa fa-arrow-up"></i>12.5%</span>

<!-- ✅ 正确：三层结构 -->
<div class="yonbi-vis-trend">
  <div class="yonbi-vis-trend__item">
    <span class="yonbi-vis-trend__label">同比</span>
    <span class="yonbi-vis-trend--up"><i class="fa fa-arrow-up"></i>12.5%</span>
  </div>
</div>
```

### 错误 4：错误的图标尺寸

```html
<!-- ❌ 错误：48px 大图标 -->
<div class="icon-wrapper" style="width:48px;height:48px">
  <i class="fas fa-coins" style="font-size:20px"></i>
</div>

<!-- ✅ 正确：20px 小图标 -->
<div class="yonbi-vis-icon-bg yonbi-vis-icon--amount">
  <i class="fa fa-coins yonbi-vis-card__icon"></i>
</div>
```
