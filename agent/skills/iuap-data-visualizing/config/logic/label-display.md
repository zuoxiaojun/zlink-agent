# 标签显示规则

---

## 标签防重叠不变量（强制）

| 配置项 | 值    | 说明        |
|------|------|-----------|
| label.show  | true | 始终尝试显示标签  |
| labelLayout.hideOverlap | true | 自动隐藏重叠的标签 |

所有含 label 的 ECharts 图表必须设置 `labelLayout: { hideOverlap: true }`，自动隐藏重叠标签。

| 实现路径 | 如何满足不变量 |
| --------- | -------------- |
| **L1 函数**（create*Option） | 函数内部已硬编码，LLM 无需手动设置 |
| **L2 组装**（generate*Series + 手写外壳） | LLM 在 option 顶层手动加 `labelLayout: { hideOverlap: true }` |
| **L3 手写 option** | LLM 在 option 顶层手动加 `labelLayout: { hideOverlap: true }` |

**适用范围**：含 `label.show: true` 的图表类型（柱/线/饼/雷达/散点/双轴/漏斗/旭日/矩形树/桑基/和弦/思维导图/瀑布/直方图等）。`label.show` 由 L1 函数模板和 L3 recipes 内置处理，LLM
照抄即可。无 label 的图表（如小提琴图 custom 无 label）不强制。

**custom 系列说明**：venn/fishbone 等用 custom renderItem 绘制文字标签的图表，`labelLayout.hideOverlap` 可能不生效（ECharts 对 custom 的 label 防重叠支持不完整），需手动控制标签位置避免重叠。

---

## 标签位置规则

| 图表类型 | 标签位置 | 说明 |
| --------- | --------- | ------ |
| 纵向柱状图 | top | 柱子顶部 |
| 横向柱状图/排名图 | right | 柱子右侧 |
| 折线图 | top | 数据点上方 |

---

## 实现代码

```javascript
// series 配置
const labelConfig = {
  show: true,              // 始终尝试显示
  position: 'top',         // 根据图表类型调整
  distance: 5,
  fontSize: 12,
  color: '#666666'
};

// option 顶层配置（L2/L3 场景手动加）
const option = {
  // ... 其他配置
  series: [...],
  labelLayout: {
    hideOverlap: true      // 自动隐藏重叠的标签
  }
};
```

**结论**：使用引擎原生防重叠机制是行业通用最佳实践。
