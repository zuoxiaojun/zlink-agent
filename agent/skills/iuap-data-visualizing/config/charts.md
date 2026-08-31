# 图表类型与选型规则

---

## 图表类型分类

| 分类 | 图表类型 |
| ------ | --------- |
| 基础图表 | bar, line, pie, scatter, effectScatter |
| 统计图表 | boxplot, heatmap, parallel, candlestick |
| 关系图表 | graph, sankey, chord |
| 层级图表 | tree, treemap, sunburst |
| 地理图表 | map, lines, geo |
| 特殊图表 | funnel, gauge, radar, themeRiver, pictorialBar |

---

## 扩展插件

| 插件名称 | CDN 地址 |
| --------- | --------- |
| echarts-wordcloud | <https://registry.npmmirror.com/echarts-wordcloud/2.1.0/files/dist/echarts-wordcloud.min.js> |
| echarts-liquidfill | <https://registry.npmmirror.com/echarts-liquidfill/3.1.0/files/dist/echarts-liquidfill.min.js> |

---

## 智能选型规则

根据数据特征自动选择最佳图表类型：

| 数据特征 | 推荐图表 |
| --------- | --------- |
| 时间序列 | line, area, candlestick |
| 分类比较 | bar, pictorialBar |
| 相关性分析 | scatter, bubble |
| 多维评估 | radar, parallel |
| 统计分布 | boxplot, violin, histogram |
| 流向/关系 | sankey, graph, chord |
| 层级结构 | tree, treemap, sunburst |
| 地理空间 | map, geo |
| 进度/完成率 | gauge, liquidFill |
| 漏斗转化 | funnel, waterfall |
| 集合关系 | venn |
| 因果分析 | fishbone |
| 文本频率 | wordCloud |
| 密度分布 | heatmap |
| 思维结构 | tree |

### 占比/构成类图表细分

| 类别数量 | 推荐图表 |
| --------- | --------- |
| ≤ 5 类 | pie（饼图） |
| 5-7 类 | donut（环图） |
| > 7 类 | treemap（矩形树图） |
| 多层级 | sunburst（旭日图） |

---

## 错误预防规则

| 问题 | 触发条件 | 处理方式 |
| ------ | --------- | --------- |
| 饼图类别过多 | 类别 > 7 | 合并为"其他"或改用柱状图 |
| 离散数据用折线 | 非时间序列 | 改用柱状图 |
| 3D 图表 | 任何场景 | 强制使用 2D |
| 散点图数据不足 | 数据点 < 15 | 提示需要更多数据 |
| 雷达图维度过多 | 维度 > 8 | 建议 5-7 个维度 |
| 饼图有负值 | 存在负数 | 改用柱状图 |
| 面积图重叠 | 多系列面积图 | 添加透明度或改用折线图 |
