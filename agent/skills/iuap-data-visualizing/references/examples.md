# 图表生成示例库

典型场景的输入→选型映射。option 配置请直接使用 SKILL.md 中的模板。

---

## 输入→选型映射表

| # | 用户意图示例 | 图表类型 | 使用模板 | 关键点 |
| --- | ------------ | --------- | --------- | -------- |
| 1 | "画个柱状图，各产品销量：饮料 9534，日用品 9149..." | `bar` | 直角坐标系 | dataset 二维数组，yAxis 加 name 单位 |
| 1b | "画个折线图展示月度趋势：1月 120，2月 135..." | `line` | 直角坐标系 | boundaryGap: false，smooth: true，areaStyle |
| 2 | "既要看销售额，也要看增长率" | `bar` + `line` 双轴 | 直角坐标系 | 双 yAxis，series 中指定 yAxisIndex |
| 2b | "画个饼图，各渠道占比" | `pie` | 非直角坐标系 | radius: ['25%','50%'], center: ['50%','45%'] 环形 |
| 2c | "画个雷达图对比两款手机" | `radar` | 非直角坐标系 | radar.indicator 配 max，series.data 嵌套数组 |
| 2d | "画个仪表盘展示 CPU 使用率 72.5%" | `gauge` | 非直角坐标系 | axisLine.lineStyle.color 分段着色 |
| 2e | "画个散点图看身高体重关系" | `scatter` | 直角坐标系 | 必须 encode: {x, y}，xAxis 改 type: 'value' |
| 2f | "画个瀑布图展示利润构成" | `bar` (stack) | 直角坐标系 | 预计算：累积值→透明底层 + 增量柱，详见 recipes/waterfall.md |
| 3 | "做个数据看板：总销售额、订单数、客单价" | 指标卡 | 模块 B | grid 布局多卡片 |
| 4 | "做个流程图：下单→付款→发货→签收" | 信息图 | 模块 C | AntV Infographic 声明式语法 |
| 5 | "52 万条每分钟温度数据画折线图" | `line` + dataZoom | 直角坐标系 | large: true，sampling: 'lttb'，animation: false |
| 6 | "标注平均线和最高点" | `bar` + markLine + markPoint | 直角坐标系 | grid.right 改为 60（标签空间） |
| 7 | "销售仪表盘：上面指标卡，下面柱状图+折线图" | 仪表盘 | 模块 D | 多 echarts.init()，共享主题，统一 resize |
| 8 | "画个桑基图展示用户来源转化" | `sankey` | 非直角坐标系 | data + links，lineStyle.color: 'gradient' |
| 9 | "画个旭日图展示部门预算分配" | `sunburst` | 非直角坐标系 | 嵌套 children，levels 分层配置 |
| 10 | "画个产权关系树图" | 层级树 | 模块 E | 纯 HTML/CSS，详见下方完整示例 |

---

## 系列生成正误对照（强制）

series 必须通过 `generate*Series` 函数生成，**禁止手写 series 对象**。手写会导致图例色与系列色脱钩。

### ❌ 错误：手写 series 对象

```javascript
series: [
  { type: 'bar', name: '销售金额', itemStyle: { color: '#3293fb' } },
  { type: 'line', name: '运费', lineStyle: { color: '#fcb530' } }
  // ↑ 漏写 itemStyle.color，图例取主题色板第 2 色 #82df2b，与线色 #fcb530 脱钩
]
```

### ✅ 正确：调用 generate*Series 函数

```javascript
series: [
  generateBarSeries('销售金额', '#3293fb'),
  generateLineSeries('运费', '#fcb530')
  // ↑ 函数内部自动同步 lineStyle.color 与 itemStyle.color，图例与线色一致
]
```

### 传色一致性

| 方式 | 是否允许 |
| ------ | --------- |
| 全不传 seriesColor（主题色板自动） | ✅ 推荐 |
| 全套传 seriesColor（语义化用色） | ✅ 允许 |
| 半传（部分传部分不传） | ❌ 禁止，图例与系列色必然脱钩 |

详见 [config/colors/series.md → 传色一致性规则](../config/colors/series.md#传色一致性规则强制)

---
