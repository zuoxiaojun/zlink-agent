# 词云（WordCloud）

> 文本词频可视化

**需要插件**：`echarts-wordcloud`，CDN 地址见 SKILL.md。

```html
<script src="https://registry.npmmirror.com/echarts/5.5.1/files/dist/echarts.min.js"></script>
<script src="https://registry.npmmirror.com/echarts-wordcloud/2.1.0/files/dist/echarts-wordcloud.min.js"></script>
```

```javascript
series: [{
  type: 'wordCloud',
  shape: 'circle',          // circle / cardioid / diamond / triangle / star
  left: 'center',
  top: 'center',
  width: '80%',
  height: '80%',
  sizeRange: [14, 60],      // 字号范围
  rotationRange: [-45, 45],  // 旋转角度范围
  rotationStep: 15,
  gridSize: 8,              // 词语间距
  drawOutOfBound: false,
  textStyle: {
    fontFamily: 'PingFang SC, Microsoft YaHei, sans-serif',
    fontWeight: 'bold',
    color: function() {
      return 'rgb(' + [
        Math.round(Math.random() * 160 + 50),
        Math.round(Math.random() * 160 + 50),
        Math.round(Math.random() * 160 + 50)
      ].join(',') + ')';
    }
  },
  emphasis: {
    textStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.15)' }
  },
  data: [
    { name: '人工智能', value: 9534 },
    { name: '机器学习', value: 7927 },
    { name: '深度学习', value: 7681 },
    { name: '自然语言', value: 6342 },
    { name: '计算机视觉', value: 5891 }
    // ... 更多词频数据
  ]
}]
```

### 词云颜色跟随主题

```javascript
// 使用 11 色系列的词云配色
color: function() {
  const palette = ['#3293fb', '#737cfd', '#82df2b', '#32c4fa', '#fcb530', '#fb6832', '#1cd46b', '#b972fc', '#77d83f', '#fba344', '#f6bd4c'];
  return palette[Math.floor(Math.random() * palette.length)];
}
```
