// 公共配置模板
// 所有图表共享的基础配置
// 引用规则：config/layout/*.md

// ======================================== 安全取值函数（强制使用）========================================
// dataset 模式下 params.value 是数组，必须使用此函数安全取值
// 详细说明见：config/logic/dataset.md

function safeGetValue(params) {
  if (Array.isArray(params.value)) {
    var colIndex = params.seriesIndex + 1;
    return params.value[colIndex];
  }
  return params.value;
}

// ======================================== 统一格式化函数（强制使用）========================================
// Y轴、tooltip、label 三处必须使用此函数，确保单位一致
// 详细说明见：config/logic/format.md

function formatUnified(value, forAxis) {
  if (value == null || typeof value !== "number" || isNaN(value)) return "--";

  var decimals = forAxis ? 1 : 2;

  if (value >= 100000000) {
    return (value / 100000000).toFixed(decimals) + "亿";
  } else if (value >= 10000) {
    return (value / 10000).toFixed(decimals) + "万";
  }
  return forAxis ? value.toLocaleString() : value.toFixed(2);
}

// ======================================== 标签显示规则 ========================================
// 详细说明见：config/logic/label-display.md
// 使用 ECharts 原生防重叠机制：labelLayout.hideOverlap: true

// 标签布局配置（自动隐藏重叠标签）
const labelLayoutConfig = {
  hideOverlap: true,
};

// ======================================== 文本像素宽度估算 ========================================
// 用于自适应 grid 计算，不依赖 DOM 渲染，纯数学估算
// 中文全角字符按 fontSize×1.0，半角字符按 fontSize×0.6

function measureTextWidth(text, fontSize) {
  if (text == null || text === "") return 0;
  fontSize = fontSize || 11;
  var w = 0;
  for (var i = 0; i < text.length; i++) {
    w += text.charCodeAt(i) > 127 ? fontSize : fontSize * 0.6;
  }
  return w;
}

// ======================================== 数值短格式 ========================================
// 仅用于自适应计算 right 时的宽度估算，不含单位时返回原始 toLocaleString

function shortenNumber(value, decimals) {
  if (value == null || typeof value !== "number" || isNaN(value)) return "--";
  decimals = decimals || 2;
  if (value >= 100000000) return (value / 100000000).toFixed(decimals) + "亿";
  if (value >= 10000) return (value / 10000).toFixed(decimals) + "万";
  return value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

// ======================================== 四维自适应 Grid 计算 ========================================
// 三层次安全策略：
//   1. containLabel: true（ECharts 原生：自动处理 left/bottom 的坐标轴标签溢出）
//   2. 数据驱动的精确计算（处理 top 和 right，因为 containLabel 不处理这两个方向）
//   3. 钳位：min=70, max=160 确保极端值不破坏布局
//
// 详细说明：config/layout/base.md → Grid 自适应章节
//
// @param source       dataset.source 二维数组
// @param chartType    'bar_vertical' | 'bar_horizontal' | 'line' | 'pie'
// @param opts         { fontSize, yAxisName, xAxisName }

function calcAdaptiveGrid(source, chartType, opts) {
  opts = opts || {};
  var fz = opts.fontSize || 11;
  var isHorizontal = chartType === "bar_horizontal";
  var sourceRows = source && source.length > 1 ? source : [];
  var sourceHeader = source && source.length > 0 ? source[0] : [];
  var seriesCount = Math.max(sourceHeader.length - 1, 0);

  // ===== TOP：标题 + toolbox + yAxis.name + series.label溢出 =====
  // title: top=8, fontSize=14 ≈ 25px
  // toolbox: top=0, itemSize=15 ≈ 15px（与title同行，取较大者）
  // 合计约 25px，加空白缓冲 15px = 40px
  // yAxis.name: nameGap(15) + fontSize(12) = 27px（从grid.top向上生长）
  // series.label溢出: position='top' + fontSize(11) + distance(5) ≈ 20px
  // 总计: 40 + 27 + 20 ≈ 87px，取整 80px（containLabel不处理这三者的溢出）
  var top = 50;
  // 默认开启：垂直柱图/折线/散点图的 yAxis 通常有 name
  // 如需关闭：传 opts.yAxisName = false（横向条图/排名图由 isHorizontal 自动关闭）
  var hasYAxisName = opts.yAxisName !== false && !isHorizontal;
  if (hasYAxisName) {
    // yAxis.name(27px) + series.label溢出(20px) + 余量(13px) = 60px增量
    // 总计 top = 50 + 30 = 80
    top += 30;
  }

  // ===== BOTTOM：图例 + 坐标轴标签 + 可选的 xAxis.name =====
  // legend: bottom=8, itemHeight=12 + lineHeight ≈ 20px
  // xAxis/value label: fontSize=11 ≈ 16px
  // 合计 ≈ 40px + 安全余量
  var bottom = 60;
  // xAxis.name 从 grid 底部往下生长，逻辑与 yAxis.name 对称
  // xAxis 保持 opt-in，只有双 value 轴图（散点图/气泡图）才需要
  if (opts.xAxisName) {
    bottom += 40;
  }

  // ===== LEFT：由 containLabel: true 自动处理 =====
  // 仅需给定最小值 70px，ECharts 会根据 Y 轴标签实际宽度自动扩张
  var left = 70;

  // ===== RIGHT：数值标签溢出（横向条图的关键问题） =====
  // containLabel 不处理 series label 的溢出，需要预计算
  var right = 70;
  if (isHorizontal && sourceRows.length > 0 && seriesCount > 0) {
    var maxLabelWidth = 0;
    for (var i = 0; i < sourceRows.length; i++) {
      var row = sourceRows[i];
      if (!row) continue;
      for (var s = 0; s < seriesCount; s++) {
        var val = row[s + 1];
        var text = "";
        if (typeof val === "number" && !isNaN(val)) {
          text = shortenNumber(val, 2);
        }
        if (text && text !== "") {
          var w = measureTextWidth(text, fz);
          if (w > maxLabelWidth) maxLabelWidth = w;
        }
      }
    }
    // 数值标签宽度 + label.distance(5) + label.padding(10) + safety(20)
    right = Math.min(Math.max(maxLabelWidth + 35, 70), 160);
  }

  return {
    top: top,
    right: right,
    bottom: bottom,
    left: left,
    containLabel: true,
  };
}

// ======================================== 公共配置模板 ========================================
// 引用自：config/layout/title.md, config/layout/legend.md

const commonConfig = {
  title: {
    left: 16,
    top: 8,
    textStyle: { fontSize: 14, fontWeight: 600, color: "#374151" },
  },
  legend: {
    bottom: 8,
    left: "center",
    itemWidth: 12,
    itemHeight: 12,
    itemGap: 16,
  },
};

// ======================================== toolbox 配置 ========================================
// 详细规则：../iuap-data-reporting/config/chart-constraints.md

// 基础 toolbox（所有图表通用，仅保存图片）
const baseToolbox = {
  show: true,
  right: 10,
  top: 0,
  itemSize: 15,
  itemGap: 10,
  feature: {
    saveAsImage: { title: "保存为图片", pixelRatio: 2 },
  },
};

// 直角坐标系 toolbox（扩展：支持切换图表类型和还原）
const cartesianToolbox = {
  show: true,
  right: 10,
  top: 0,
  itemSize: 15,
  itemGap: 10,
  feature: {
    saveAsImage: { title: "保存为图片", pixelRatio: 2 },
    magicType: {
      type: ["line", "bar"],
      title: { line: "折线图", bar: "柱状图" },
    },
    restore: { title: "还原" },
  },
};

// ======================================== grid 配置 ========================================
// 引用自：config/layout/grid.md

const gridTemplate = {
  top: 60,
  right: 70,
  left: 70,
  bottom: 60,
  containLabel: true,
};

function getResponsiveGrid(containerWidth) {
  if (containerWidth < 500) {
    return { top: 50, right: 50, left: 50, bottom: 50 };
  } else if (containerWidth < 700) {
    return { top: 55, right: 60, left: 60, bottom: 55 };
  }
  return { top: 60, right: 70, left: 70, bottom: 60 };
}

// ======================================== 系列色配置 ========================================
// 引用自：config/colors/series.md

const seriesColors = [
  "#3293fb",
  "#737cfd",
  "#82df2b",
  "#32c4fa",
  "#fcb530",
  "#fb6832",
  "#1cd46b",
  "#b972fc",
  "#77d83f",
  "#fba344",
  "#f6bd4c",
];

// ======================================== dataZoom 与 legend 共存配方 ========================================
// 引用自：config/layout/base.md → dataZoom 与 legend 共存布局
// 当 dataZoom slider 与 legend 同时存在时，必须使用此配方，禁止手写 bottom 值
// 垂直堆叠：slider(bottom 8) → legend(bottom 38) → grid(bottom 80)

const dataZoomWithLegend = [
  { type: "inside", start: 0, end: 100 },
  {
    type: "slider",
    start: 0,
    end: 100,
    bottom: 8,
    height: 22,
    borderColor: "#ddd",
    fillerColor: "rgba(50,147,251,0.1)",
  },
];

const legendWithZoom = {
  show: true,
  bottom: 38,
  left: "center",
  itemWidth: 12,
  itemHeight: 12,
  itemGap: 16,
};

// ======================================== tooltip 格式化 ========================================

function formatTooltip(params) {
  var v = safeGetValue(params);
  return formatUnified(v, false);
}

function formatTooltipAxis(params) {
  if (!params || params.length === 0) return "";
  var lines = params.map((p) => {
    var v = safeGetValue(p);
    return p.seriesName + ": " + formatUnified(v, false);
  });
  return params[0].name + "<br/>" + lines.join("<br/>");
}
