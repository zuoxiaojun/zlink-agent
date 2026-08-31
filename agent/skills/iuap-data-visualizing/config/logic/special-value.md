# 特殊值处理

---

## 处理规则

| 情况 | 显示值 |
| ------ | -------- |
| null | -- |
| undefined | -- |
| NaN | -- |
| zero | 0 |

---

## 实现代码

```javascript
function handleSpecialValue(value) {
  if (value == null || isNaN(value)) return '--';
  if (value === 0) return '0';
  return value;
}
```

---

## 在 formatter 中使用

```javascript
formatter: function(params) {
  var v = safeGetValue(params);
  if (v == null || isNaN(v)) return '--';
  // 正常格式化逻辑
}
```
