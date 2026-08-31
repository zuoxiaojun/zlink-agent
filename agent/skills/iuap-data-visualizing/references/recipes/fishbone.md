# 鱼骨图（Fishbone / Ishikawa）

> 因果分析图：右侧结果 → 左侧各大骨（大类原因）→ 各骨上的小骨（具体原因）

**实现原理**：ECharts `custom` renderItem 绘制线条 + 文字。

```javascript
series: [{
  type: 'custom',
  coordinateSystem: 'none',
  renderItem: function(params, api) {
    const children = [];
    const cx = 700, cy = 220;  // 鱼头中心（结果标签）
    const tailX = 80;          // 鱼尾 X
    const spineY = cy;         // 主脊柱 Y

    // 主脊柱线
    children.push({
      type: 'line',
      shape: { x1: tailX, y1: spineY, x2: cx + 40, y2: spineY },
      style: { stroke: '#374151', lineWidth: 3 }
    });

    // 鱼头（三角形）
    children.push({
      type: 'polygon',
      shape: { points: [[cx + 40, spineY - 30], [cx + 80, spineY], [cx + 40, spineY + 30]] },
      style: { fill: '#3293fb', stroke: '#3293fb', lineWidth: 1 }
    });

    // 结果标签
    children.push({
      type: 'text',
      style: { text: '问题/结果', x: cx + 50, y: spineY, fill: '#fff', fontSize: 13, fontWeight: 600, textAlign: 'center', textVerticalAlign: 'middle' }
    });

    // 大骨数据：上方和下方交替排列
    const bones = [
      { label: '人员', causes: ['经验不足', '培训不够', '人员流动'], side: 'top' },
      { label: '方法', causes: ['流程不规范', '标准缺失'], side: 'top' },
      { label: '设备', causes: ['老化', '维护不足'], side: 'bottom' },
      { label: '环境', causes: ['温度', '湿度', '噪声'], side: 'bottom' }
    ];

    const boneSpacing = 130;
    bones.forEach((bone, i) => {
      const bx = cx - 60 - i * boneSpacing / 2;
      const boneLen = 100;
      const endY = bone.side === 'top' ? spineY - boneLen : spineY + boneLen;

      // 大骨线（45度斜线）
      children.push({
        type: 'line',
        shape: { x1: bx, y1: spineY, x2: bx + boneLen * 0.6, y2: endY },
        style: { stroke: '#8b949e', lineWidth: 2 }
      });

      // 大骨标签
      const labelY = bone.side === 'top' ? endY - 16 : endY + 16;
      children.push({
        type: 'text',
        style: {
          text: bone.label, x: bx + boneLen * 0.3, y: labelY,
          fill: '#374151', fontSize: 13, fontWeight: 600, textAlign: 'center'
        }
      });

      // 小骨（平行于主脊柱的短线）
      bone.causes.forEach((cause, j) => {
        const ratio = (j + 1) / (bone.causes.length + 1);
        const sx = bx + (boneLen * 0.6) * ratio;
        const sy = spineY + (endY - spineY) * ratio;
        const smallLen = 30;
        const smallEndY = bone.side === 'top' ? sy - smallLen : sy + smallLen;

        children.push({
          type: 'line',
          shape: { x1: sx, y1: sy, x2: sx, y2: smallEndY },
          style: { stroke: '#c9d1d9', lineWidth: 1 }
        });

        children.push({
          type: 'text',
          style: {
            text: cause, x: sx, y: bone.side === 'top' ? smallEndY - 6 : smallEndY + 14,
            fill: '#595959', fontSize: 11, textAlign: 'center'
          }
        });
      });
    });

    return { type: 'group', children };
  },
  data: [0],
  animation: false
}],
labelLayout: { hideOverlap: true }  // custom 系列：手动控制标签位置避免重叠
```
