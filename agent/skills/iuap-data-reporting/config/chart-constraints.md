# 图表配置约束

> 本规则引用可视化技能的布局规则。

---

## 布局规则（真理源）

**详细规则** → [../iuap-data-visualizing/config/layout/base.md](../iuap-data-visualizing/config/layout/base.md)

包含：标题配置、图例配置、Grid 配置、容器配置、常见错误对照表

---

## 模板来源（报告引用）

| 图表类型 | 模板文件 |
|----------|----------|
| 直角坐标系图表 | [option_cartesian.js](../iuap-data-visualizing/templates/echarts/option_cartesian.js) |
| 非直角坐标系图表 | [option_non_cartesian.js](../iuap-data-visualizing/templates/echarts/option_non_cartesian.js) |

---

## 报告图表调用要点

1. **响应式 Grid**：使用 `getResponsiveGrid(container)` 函数（定义在 `base.html` 的 `<head>` 中）

2. **图例强制显示**：必须设置 `legend.show: true`，否则单系列图表图例不显示

3. **技能栏（toolbox）**：
   - **直角坐标系图表**（bar/line/area）必须包含：

     ```javascript
     toolbox: {
       show: true,
       right: 10,
       top: 0,
       feature: {
         saveAsImage: { title: '保存为图片', pixelRatio: 2 },
         magicType: { type: ['line', 'bar'], title: { line: '折线图', bar: '柱状图' } },
         restore: { title: '还原' }
       }
     }
     ```

   - **非直角坐标系图表**（pie/radar/scatter 等）只需：

     ```javascript
     toolbox: {
       show: true,
       right: 10,
       top: 0,
       feature: {
         saveAsImage: { title: '保存为图片', pixelRatio: 2 }
       }
     }
     ```

4. **禁止事项**：禁止自行编写 legend/title 配置、禁止自定义主题或颜色

5. **容器规范**：必须内嵌 loading 占位符
