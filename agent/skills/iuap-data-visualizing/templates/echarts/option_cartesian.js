/**
 * 直角坐标系图表 option 模板
 *
 * 定位：LLM 参考模板（非运行时模块）
 *   - 本文件不被 require，没有 module.exports
 *   - LLM 生成 bar / line / area / scatter 图表时，参考本文件的模板配置，
 *     照抄到输出的 ECharts option 中
 *   - boxplot / candlestick 无专属模板，需 LLM 自行编写或走 dynamic_executor
 *   - 与 config/styles/*.md（bar.md / line.md）配合：
 *     .md 讲样式规则，本文件给代码模板
 *
 * 依赖（来自 common.js，LLM 需自行合并到输出 option）：
 *   - commonConfig     → title / legend 基础配置
 *   - cartesianToolbox → toolbox 配置（saveAsImage + magicType + restore）
 *   - formatUnified / safeGetValue → 数值格式化与安全取值
 *   - calcAdaptiveGrid → 四维自适应 grid 计算
 *
 * 组装流程：
 *   - 垂直柱图/折线/面积：调 generateXxxSeries() 拿 series → 调
 *     createCartesianOption(title, legendData, datasetSource, seriesConfig, gridConfig)
 *   - 横向条图/排名图：调 generateHorizontalBarSeries() 拿 series → 调
 *     createHorizontalCartesianOption(title, legendData, datasetSource, seriesConfig)
 *   - 散点图/气泡图：调 createScatterOption(title, datasetSource, xName, yName, seriesConfig, gridConfig)
 *
 * 数据模式（createCartesianOption / createScatterOption 自动判断）：
 *   - dataset 模式：datasetSource 为二维数组 [['预算','执行'],[100,200],...] → 自动设 dataset.source
 *   - series.data 模式：datasetSource 传 null，数据在 seriesConfig 每项的 data 字段
 *
 * 样式规则：config/styles/bar.md, config/styles/line.md
 * 公共配置：common.js
 */

// ======================================== 柱状图样式配置 ========================================
// 详细规则：config/styles/bar.md

const barSeriesTemplate = {
  type: "bar",
  barCategoryGap: "70%",
  itemStyle: {
    barBorderRadius: [3, 3, 0, 0],
  },
  label: {
    show: true,
    position: "top",
    distance: 5,
    fontSize: 12,
    color: "#666666",
    formatter: (params) => formatUnified(safeGetValue(params), false),
  },
};

const barHorizontalTemplate = {
  type: "bar",
  barCategoryGap: "70%",
  itemStyle: {
    barBorderRadius: [0, 3, 3, 0],
  },
  label: {
    show: true,
    position: "right",
    distance: 5,
    fontSize: 12,
    color: "#666666",
    formatter: (params) => formatUnified(safeGetValue(params), false),
  },
};

// ======================================== 折线图样式配置 ========================================
// 详细规则：config/styles/line.md

const lineSeriesTemplate = {
  type: "line",
  smooth: true,
  lineStyle: { width: 1 },
  symbol: "emptyCircle",
  symbolSize: 4,
  label: {
    show: true,
    position: "top",
    distance: 5,
    fontSize: 12,
    color: "#666666",
    formatter: (params) => formatUnified(safeGetValue(params), false),
  },
};

const areaSeriesTemplate = {
  type: "line",
  smooth: true,
  lineStyle: { width: 1 },
  symbol: "emptyCircle",
  symbolSize: 4,
  areaStyle: { opacity: 0.3 },
  label: {
    show: true,
    position: "top",
    distance: 5,
    fontSize: 12,
    color: "#666666",
    formatter: (params) => formatUnified(safeGetValue(params), false),
  },
};

// ======================================== 渐变色生成函数 ========================================

function generateGradientColor(seriesColor, chartType) {
  const hex = seriesColor.replace("#", "");
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);
  const lightColor = `rgba(${r},${g},${b},0.7)`;

  if (chartType === "bar" || chartType === "bar_vertical") {
    return {
      type: "linear",
      x: 0,
      y: 0,
      x2: 0,
      y2: 1,
      colorStops: [
        { offset: 0, color: seriesColor },
        { offset: 1, color: lightColor },
      ],
    };
  } else if (chartType === "bar_horizontal") {
    return {
      type: "linear",
      x: 0,
      y: 0,
      x2: 1,
      y2: 0,
      colorStops: [
        { offset: 0, color: lightColor },
        { offset: 1, color: seriesColor },
      ],
    };
  }
  return seriesColor;
}

// ======================================== 系列配置生成函数 ========================================

function generateBarSeries(seriesName, seriesColor, seriesCount) {
  var result = {
    ...barSeriesTemplate,
    name: seriesName,
    label: { ...barSeriesTemplate.label },
  };
  // LLM 传色才设，否则主题色板自动接管（第 1 个系列 = #3293fb 主体色）
  if (seriesColor) {
    result.itemStyle = {
      ...result.itemStyle,
      color: generateGradientColor(seriesColor, "bar"),
    };
  }
  return result;
}

function generateHorizontalBarSeries(seriesName, seriesColor, seriesCount) {
  var result = {
    ...barHorizontalTemplate,
    name: seriesName,
    label: { ...barHorizontalTemplate.label },
  };
  if (seriesColor) {
    result.itemStyle = {
      ...result.itemStyle,
      color: generateGradientColor(seriesColor, "bar_horizontal"),
    };
  }
  return result;
}

function generateLineSeries(seriesName, seriesColor, seriesCount) {
  var result = {
    ...lineSeriesTemplate,
    name: seriesName,
    label: { ...lineSeriesTemplate.label },
  };
  if (seriesColor) {
    result.lineStyle = { width: 1, color: seriesColor };
    result.itemStyle = { color: seriesColor };
  }
  return result;
}

function generateAreaSeries(seriesName, seriesColor, seriesCount) {
  var result = {
    ...areaSeriesTemplate,
    name: seriesName,
    label: { ...areaSeriesTemplate.label },
  };
  if (seriesColor) {
    result.lineStyle = { width: 1, color: seriesColor };
    result.itemStyle = { color: seriesColor };
    result.areaStyle = {
      color: {
        type: "linear",
        x: 0,
        y: 0,
        x2: 0,
        y2: 1,
        colorStops: [
          { offset: 0, color: seriesColor },
          { offset: 1, color: "rgba(255,255,255,0.1)" },
        ],
      },
      opacity: 0.3,
    };
  }
  return result;
}

// ======================================== 完整 option 模板 ========================================

function createCartesianOption(
  title,
  legendData,
  datasetSource,
  seriesConfig,
  gridConfig,
) {
  // 兼容 dataset 和 series.data 两种数据模式
  var isDatasetMode =
    Array.isArray(datasetSource) &&
    Array.isArray(datasetSource[0]) &&
    !datasetSource[0].name;
  return {
    title: {
      ...commonConfig.title,
      text: title,
    },
    tooltip: {
      trigger: "axis",
      formatter: formatTooltipAxis,
    },
    legend: {
      ...commonConfig.legend,
      data: legendData,
    },
    toolbox: cartesianToolbox,
    ...(isDatasetMode ? { dataset: { source: datasetSource } } : {}),
    // 未传 gridConfig 时自动使用 calcAdaptiveGrid 计算四维自适应值
    grid: gridConfig || calcAdaptiveGrid(datasetSource, "bar_vertical"),
    xAxis: {
      type: "category",
      axisLabel: {
        interval: "auto",
        rotate: 0,
        overflow: "truncate",
        width: 80,
      },
    },
    yAxis: {
      type: "value",
      nameLocation: "end",
      nameGap: 15,
      axisLabel: {
        formatter: (value) => formatUnified(value, true),
      },
    },
    series: seriesConfig,
    labelLayout: {
      hideOverlap: true,
    },
    animation: true,
    animationDuration: 800,
  };
}

// ======================================== 横向条图完整 option 模板 ========================================
// 与 createCartesianOption 的区别：
//   1. xAxis: 'value', yAxis: 'category'（坐标轴翻转）
//   2. grid 使用 bar_horizontal 自适应策略（自动计算右侧数值标签溢出）
//   3. Y 轴标签 fontSize 固定 11px
//
// 适合场景：排名图、对比图、长标签类目图
// 使用方式：直接调用，不需要传递 gridConfig

function createHorizontalCartesianOption(
  title,
  legendData,
  datasetSource,
  seriesConfig,
) {
  // 兼容 dataset 和 series.data 两种数据模式
  var isDatasetMode =
    Array.isArray(datasetSource) &&
    Array.isArray(datasetSource[0]) &&
    !datasetSource[0].name;
  return {
    title: {
      ...commonConfig.title,
      text: title,
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: formatTooltipAxis,
    },
    legend: {
      ...commonConfig.legend,
      data: legendData,
    },
    toolbox: cartesianToolbox,
    ...(isDatasetMode ? { dataset: { source: datasetSource } } : {}),
    grid: calcAdaptiveGrid(datasetSource, "bar_horizontal"),
    xAxis: {
      type: "value",
      axisLabel: {
        formatter: (value) => formatUnified(value, true),
      },
    },
    yAxis: {
      type: "category",
      axisLabel: {
        fontSize: 11,
      },
    },
    series: seriesConfig,
    labelLayout: {
      hideOverlap: true,
    },
    animation: true,
    animationDuration: 800,
  };
}

// ======================================== 散点图/气泡图完整 option 模板 ========================================
// 与 createCartesianOption 的区别：
//   1. xAxis: 'value', yAxis: 'value'（双 value 轴）
//   2. tooltip: trigger: 'item'（散点图按点触发，非按轴触发）
//   3. grid 使用 scatter 自适应策略（xAxis.name 和 yAxis.name 都需要额外空间）
//   4. 直接接收 xName/yName 参数，无需 LLM 手写 name 字段
//   5. 默认 label: { show: false }（散点图/气泡图数据点密集，标签互相遮盖）
//
// 适合场景：散点图、气泡图、分布图
// 使用方式：createScatterOption(title, datasetSource, xName, yName, seriesConfig, gridConfig)
//
// 标签说明：散点图/气泡图默认不展示 data label，信息通过 tooltip 展示
// 如需展示标签，在 seriesConfig 中显式设置 label: { show: true, position: 'right' }
//
// 数据格式兼容：
//   方式1（dataset 模式）：datasetSource 为二维数组 [['预算','执行'], [100,200], ...]
//      → 自动设 dataset.source，series 通过 encode 映射坐标轴
//   方式2（series.data 模式）：datasetSource 传 null，数据在 seriesConfig 每项的 data 字段中
//      → 不设 dataset，数据直接从 series.data 读取
//   自动判断规则：datasetSource 是二维数组且首元素无 name 属性 → 方式1，否则不设 dataset

function createScatterOption(
  title,
  datasetSource,
  xName,
  yName,
  seriesConfig,
  gridConfig,
) {
  // 判断是否为 dataset 模式：二维数组且首行不是 {name, value} 格式
  var isDatasetMode =
    Array.isArray(datasetSource) &&
    Array.isArray(datasetSource[0]) &&
    !datasetSource[0].name;
  return {
    title: {
      ...commonConfig.title,
      text: title,
    },
    tooltip: {
      trigger: "item",
      formatter: (params) => {
        var d = params.data;
        var parts = [];
        if (xName) parts.push(xName + ": " + formatUnified(d[0], false));
        if (yName) parts.push(yName + ": " + formatUnified(d[1], false));
        return (d[2] || d.name || "") + "<br/>" + parts.join("<br/>");
      },
    },
    legend: {
      ...commonConfig.legend,
    },
    toolbox: baseToolbox,
    ...(isDatasetMode ? { dataset: { source: datasetSource } } : {}),
    grid:
      gridConfig ||
      calcAdaptiveGrid(datasetSource, "scatter", { xAxisName: true }),
    xAxis: {
      type: "value",
      name: xName,
      nameTextStyle: { color: "#666666", fontSize: 12 },
      axisLabel: {
        formatter: (value) => formatUnified(value, true),
      },
    },
    yAxis: {
      type: "value",
      name: yName,
      nameTextStyle: { color: "#666666", fontSize: 12 },
      axisLabel: {
        formatter: (value) => formatUnified(value, true),
      },
    },
    series: seriesConfig.map((s) => {
      // 散点图/气泡图默认不展示 data label（数据点密集时标签互相遮盖）
      // 信息通过 tooltip 展示。如需展示标签，在 seriesConfig 中显式设置 label
      if (s.label === undefined) {
        return Object.assign({}, s, { label: { show: false } });
      }
      return s;
    }),
    labelLayout: {
      hideOverlap: true,
    },
    animation: true,
    animationDuration: 800,
  };
}

// ======================================== 双轴图完整 option 模板 ========================================
// 适用场景：双 yAxis（左轴+右轴），每轴对应 1 个系列（如柱图+折线图组合）
// 与 createCartesianOption 的区别：
//   1. yAxis 为数组（2 个轴），series 通过 yAxisIndex 指定归属轴
//   2. 每个 yAxis 的 nameTextStyle.color 自动与该轴对应系列的 seriesColor 同步
//   3. series 强制走 generateBarSeries/generateLineSeries，禁止手写绕过系列色管控
//
// 使用方式：
//   createDualAxisOption(title, legendData, datasetSource, seriesConfig, yAxisConfig)
//   - seriesConfig: [{ type: 'bar'/'line', yAxisIndex: 0/1 }]
//   - yAxisConfig:  [{ name: '轴名称', seriesColor: '#xxxxxx' }]
//   - yAxisConfig 与 yAxisIndex 一一对应
//
// 系列色规则：
//   - 传 seriesColor → 用传入的色（语义化场景）
//   - 不传 seriesColor → 按 11 色板顺序自动补位（第 1 轴 #3293fb，第 2 轴 #737cfd）

function createDualAxisOption(
  title,
  legendData,
  datasetSource,
  seriesConfig,
  yAxisConfig,
) {
  var isDatasetMode =
    Array.isArray(datasetSource) &&
    Array.isArray(datasetSource[0]) &&
    !datasetSource[0].name;

  // 默认系列色（11 色板前 2 色）
  var defaultColors = ["#3293fb", "#737cfd"];

  // 构建 yAxis：每轴 nameTextStyle.color 与对应 seriesColor 同步
  var yAxis = yAxisConfig.map((cfg, idx) => {
    var color = cfg.seriesColor || defaultColors[idx];
    return {
      type: "value",
      name: cfg.name,
      nameTextStyle: { color: color, fontSize: 12 },
      nameLocation: "end",
      nameGap: 15,
      axisLabel: {
        formatter: (value) => formatUnified(value, true),
      },
    };
  });

  // 构建 series：强制走 generate*Series，按 type 调用对应函数
  var series = seriesConfig.map((cfg, idx) => {
    var yAxisIdx = cfg.yAxisIndex || 0;
    var color =
      (yAxisConfig[yAxisIdx] && yAxisConfig[yAxisIdx].seriesColor) ||
      defaultColors[yAxisIdx];
    var seriesName = legendData[idx];

    var generated;
    if (cfg.type === "bar") {
      generated = generateBarSeries(seriesName, color);
    } else if (cfg.type === "line") {
      generated = generateLineSeries(seriesName, color);
    } else {
      // 其他类型（area 等）降级为 line 模板
      generated = generateLineSeries(seriesName, color);
    }
    generated.yAxisIndex = yAxisIdx;
    return generated;
  });

  return {
    title: {
      ...commonConfig.title,
      text: title,
    },
    tooltip: {
      trigger: "axis",
      formatter: formatTooltipAxis,
    },
    legend: {
      ...commonConfig.legend,
      data: legendData,
    },
    toolbox: cartesianToolbox,
    ...(isDatasetMode ? { dataset: { source: datasetSource } } : {}),
    grid: calcAdaptiveGrid(datasetSource, "bar_vertical"),
    xAxis: {
      type: "category",
      axisLabel: {
        interval: "auto",
        rotate: 0,
        overflow: "truncate",
        width: 80,
      },
    },
    yAxis: yAxis,
    series: series,
    labelLayout: {
      hideOverlap: true,
    },
    animation: true,
    animationDuration: 800,
  };
}
