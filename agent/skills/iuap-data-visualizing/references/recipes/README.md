# 特殊图表配方速查表

本目录包含非常规图表的实现配方，按需加载。

---

## 配方索引

| 图表 | 文件 | 实现方式 | 需要插件 | 复杂度 |
| ------ | ------ | --------- | --------- | ------- |
| 瀑布图 | [waterfall.md](waterfall.md) | `bar` (stack) | 否 | 中 |
| 韦恩图 | [venn.md](venn.md) | `custom` | 否 | 中 |
| 鱼骨图 | [fishbone.md](fishbone.md) | `custom` | 否 | 高 |
| 小提琴图 | [violin.md](violin.md) | `custom` + KDE | 否 | 高 |
| 思维导图 | [mindmap.md](mindmap.md) | `tree` (radial) | 否 | 低 |
| 直方图 | [histogram.md](histogram.md) | `bar` + 分箱 | 否 | 中 |
| 词云 | [wordcloud.md](wordcloud.md) | `wordCloud` | 是 | 低 |
| 水球图 | [liquidfill.md](liquidfill.md) | `liquidFill` | 是 | 低 |
| 旭日图 | [sunburst.md](sunburst.md) | `sunburst` | 否 | 低 |
| 矩形树图 | [treemap.md](treemap.md) | `treemap` | 否 | 低 |
| 桑基图 | [sankey.md](sankey.md) | `sankey` | 否 | 低 |
| 和弦图 | [chord.md](chord.md) | `graph` (circular) | 否 | 中 |
| 层级树状图 | [hierarchy-tree.md](hierarchy-tree.md) | 纯 HTML/CSS | 否 | 中 |
| 信息图 | [infographic.md](infographic.md) | AntV Infographic | 是 | 低 |

---

## 使用方式

**仅当用户明确请求该图表类型时，才读取对应的配方文件。**

示例：

- 用户请求"画个瀑布图" → 读取 `waterfall.md`
- 用户请求"画个产权关系树" → 读取 `hierarchy-tree.md`
- 用户请求"画个流程图/信息图" → 读取 `infographic.md`
- 用户请求"画个柱状图" → 不需要读取任何配方文件（使用 SKILL.md 中的内置模板）
