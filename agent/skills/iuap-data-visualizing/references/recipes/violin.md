# 小提琴图（Violin Plot）

> 展示数据分布密度，是箱线图的增强版

**实现原理**：先计算核密度估计（KDE），再用 `custom` renderItem 绘制对称密度曲线。

### 密度计算

```javascript
function kernelDensityEstimate(data, bandwidth, points) {
  // 高斯核密度估计
  const n = data.length;
  const result = [];
  const min = Math.min(...data);
  const max = Math.max(...data);
  const step = (max - min) / points;

  for (let i = 0; i <= points; i++) {
    const x = min + i * step;
    let sum = 0;
    for (let j = 0; j < n; j++) {
      const u = (x - data[j]) / bandwidth;
      sum += Math.exp(-0.5 * u * u) / Math.sqrt(2 * Math.PI);
    }
    result.push({ x, y: sum / (n * bandwidth) });
  }
  // 归一化到 [0, 1]
  const maxY = Math.max(...result.map(r => r.y));
  result.forEach(r => r.y /= maxY);
  return result;
}

// Silverman 法则自动选择带宽
function silvermanBandwidth(data) {
  const n = data.length;
  const mean = data.reduce((a, b) => a + b, 0) / n;
  const std = Math.sqrt(data.reduce((a, b) => a + (b - mean) ** 2, 0) / n);
  const iqr = data.sort((a, b) => a - b);
  const q1 = iqr[Math.floor(n * 0.25)];
  const q3 = iqr[Math.floor(n * 0.75)];
  return 0.9 * Math.min(std, (q3 - q1) / 1.34) * Math.pow(n, -0.2);
}
```

### 渲染

```javascript
series: [{
  type: 'custom',
  renderItem: function(params, api) {
    // 每个分类一组数据
    const categoryIndex = api.value(0);
    const rawData = api.value(1);  // 原始数据数组
    const bandwidth = silvermanBandwidth(rawData);
    const density = kernelDensityEstimate(rawData, bandwidth, 50);

    // 在 category 坐标上绘制对称密度曲线
    const categoryCenter = api.coord([0, categoryIndex])[1];
    const halfWidth = api.size([0, 1])[1] * 0.35;
    const points = [];

    // 右侧密度曲线
    density.forEach(d => {
      const x = api.coord([d.x, 0])[0];
      points.push([x, categoryCenter - d.y * halfWidth]);
    });
    // 左侧密度曲线（镜像）
    density.slice().reverse().forEach(d => {
      const x = api.coord([d.x, 0])[0];
      points.push([x, categoryCenter + d.y * halfWidth]);
    });

    return {
      type: 'polygon',
      shape: { points: points },
      style: {
        fill: 'rgba(50,147,251,0.3)',
        stroke: '#3293fb',
        lineWidth: 1.5
      }
    };
  },
  data: [
    [0, [/* 分类A 的原始数据 */]],
    [1, [/* 分类B 的原始数据 */]]
  ],
  animation: false
}]
```
