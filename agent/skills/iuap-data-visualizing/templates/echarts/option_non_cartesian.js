/**
 * 非直角坐标系图表 option 模板
 *
 * 定位：LLM 参考模板（非运行时模块）
 *   - 本文件不被 require，没有 module.exports
 *   - LLM 生成 pie / donut / radar / gauge / funnel 图表时，参考本文件的模板配置，
 *     照抄到输出的 ECharts option 中
 *   - 与 config/styles/*.md（pie.md / radar.md / other.md）配合：
 *     .md 讲样式规则（center / radius / labelLine 等取值原则），本文件给代码模板
 *
 * 依赖（来自 common.js，LLM 需自行合并到输出 option）：
 *   - commonConfig  → title / legend 基础配置
 *   - baseToolbox   → toolbox 配置（仅 saveAsImage，非直角坐标系不用 magicType）
 *
 * 组装流程：
 *   - pie / donut / funnel / gauge：调 generateXxxSeries() 拿 series → 调
 *     createNonCartesianOption(title, series) 拿外壳 option
 *   - radar：调 generateRadarOption(indicators) 拿 radar 坐标系配置 → 调
 *     generateRadarSeries() 拿 series → 调 createNonCartesianOption(title, series)
 *     拿外壳 → 把 radar 配置 spread 合并进外壳
 *
 * 样式规则：config/styles/pie.md, config/styles/radar.md, config/styles/other.md
 * 公共配置：common.js
 */

// ======================================== 饼图样式配置 ========================================
// 详细规则：config/styles/pie.md

const pieSeriesTemplate = {
  type: "pie",
  center: ["50%", "50%"],
  radius: "60%",
  avoidLabelOverlap: true,
  label: {
    show: true,
    position: "outside",
    formatter: "{b}\n{d}%",
    fontSize: 12,
    color: "inherit",
  },
  labelLine: {
    show: true,
    length: 10,
    length2: 10,
  },
  itemStyle: {
    borderRadius: 3,
    borderColor: "#fff",
    borderWidth: 2,
  },
  emphasis: {
    label: {
      show: true,
      fontSize: 14,
      fontWeight: "bold",
    },
  },
};

const donutSeriesTemplate = {
  ...pieSeriesTemplate,
  radius: ["40%", "60%"],
  emphasis: {
    label: {
      show: true,
      fontSize: 14,
      fontWeight: "bold",
    },
    itemStyle: {
      shadowBlur: 10,
      shadowOffsetX: 0,
      shadowColor: "rgba(0, 0, 0, 0.5)",
    },
  },
};

// ======================================== 雷达图样式配置 ========================================
// 详细规则：config/styles/radar.md

const radarSeriesTemplate = {
  type: "radar",
  symbol: "emptyCircle",
  symbolSize: 4,
  lineStyle: { width: 1 },
  areaStyle: { opacity: 0.3 },
  label: {
    show: true,
    fontSize: 12,
  },
};

function generateRadarOption(indicators) {
  return {
    radar: {
      indicator: indicators,
      shape: "polygon",
      splitNumber: 5,
      axisName: {
        color: "#666",
        fontSize: 12,
      },
      splitLine: {
        lineStyle: { color: "#e5e7eb" },
      },
      splitArea: {
        show: true,
        areaStyle: { color: ["rgba(50,147,251,0.05)", "rgba(50,147,251,0.1)"] },
      },
      axisLine: {
        lineStyle: { color: "#e5e7eb" },
      },
    },
  };
}

// ======================================== 漏斗图样式配置 ========================================
// 详细规则：config/styles/other.md

const funnelSeriesTemplate = {
  type: "funnel",
  left: "10%",
  top: 60,
  bottom: 60,
  width: "80%",
  min: 0,
  max: 100,
  minSize: "0%",
  maxSize: "100%",
  sort: "descending",
  gap: 2,
  label: {
    show: true,
    position: "inside",
    formatter: "{b}: {c}",
    fontSize: 12,
  },
  labelLine: {
    length: 10,
    lineStyle: { width: 1, type: "solid" },
  },
  itemStyle: {
    borderWidth: 0,
    borderColor: "#fff",
  },
  emphasis: {
    label: { fontSize: 14 },
  },
};

// ======================================== 仪表盘样式配置 ========================================
// 详细规则：config/styles/other.md

const gaugeSeriesTemplate = {
  type: "gauge",
  center: ["50%", "60%"],
  radius: "70%",
  startAngle: 200,
  endAngle: -20,
  min: 0,
  max: 100,
  splitNumber: 10,
  axisLine: {
    lineStyle: {
      width: 10,
      color: [
        [0.3, "#fb6832"],
        [0.7, "#fcb530"],
        [1, "#1cd46b"],
      ],
    },
  },
  pointer: {
    icon: "path://M12.8,0.7l12,40H-0.2l12-40z",
    length: "60%",
    width: 8,
    offsetCenter: [0, "-10%"],
    itemStyle: { color: "auto" },
  },
  axisTick: {
    length: 8,
    lineStyle: { color: "auto", width: 1 },
  },
  splitLine: {
    length: 12,
    lineStyle: { color: "auto", width: 2 },
  },
  axisLabel: {
    color: "#666",
    fontSize: 12,
    distance: -40,
    formatter: (value) => {
      if (value === 0) return "0";
      if (value === 100) return "100";
      return value;
    },
  },
  title: { offsetCenter: [0, "30%"], fontSize: 14 },
  detail: {
    valueAnimation: true,
    fontSize: 24,
    offsetCenter: [0, "50%"],
    formatter: "{value}%",
    color: "auto",
  },
};

// ======================================== 系列配置生成函数 ========================================

function generatePieSeries(data, colors) {
  // 不传 colors 时，主题色板自动按 data index 着色（第 1 个扇区 = #3293fb 主体色）
  if (!colors) {
    return { ...pieSeriesTemplate, data: data };
  }
  return {
    ...pieSeriesTemplate,
    data: data.map((item, index) => ({
      name: item.name,
      value: item.value,
      itemStyle: {
        color: colors[index % colors.length],
        borderRadius: 3,
        borderColor: "#fff",
        borderWidth: 2,
      },
    })),
  };
}

function generateDonutSeries(data, colors) {
  if (!colors) {
    return { ...donutSeriesTemplate, data: data };
  }
  return {
    ...donutSeriesTemplate,
    data: data.map((item, index) => ({
      name: item.name,
      value: item.value,
      itemStyle: {
        color: colors[index % colors.length],
        borderRadius: 3,
        borderColor: "#fff",
        borderWidth: 2,
      },
    })),
  };
}

function generateRadarSeries(seriesName, data, color) {
  var result = {
    ...radarSeriesTemplate,
    name: seriesName,
    value: data,
  };
  // LLM 传色才设，否则主题色板自动接管
  if (color) {
    result.lineStyle = { width: 1, color: color };
    result.areaStyle = { color: color, opacity: 0.3 };
    result.itemStyle = { color: color };
  }
  return result;
}

// ======================================== 完整 option 模板 ========================================

function createNonCartesianOption(title, seriesConfig) {
  return {
    title: {
      ...commonConfig.title,
      text: title,
    },
    tooltip: { trigger: "item" },
    legend: {
      ...commonConfig.legend,
    },
    toolbox: baseToolbox,
    series: seriesConfig,
    labelLayout: {
      hideOverlap: true,
    },
  };
}
