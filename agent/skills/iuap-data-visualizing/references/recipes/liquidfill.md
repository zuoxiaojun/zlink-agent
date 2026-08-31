# 水球图（Liquid Fill）

> 进度/完成率的动态展示

**需要插件**：`echarts-liquidfill`，CDN 地址见 SKILL.md。

```html
<script src="https://registry.npmmirror.com/echarts/5.5.1/files/dist/echarts.min.js"></script>
<script src="https://registry.npmmirror.com/echarts-liquidfill/3.1.0/files/dist/echarts-liquidfill.min.js"></script>
```

```javascript
series: [{
  type: 'liquidFill',
  data: [0.68],             // 0-1 之间的值
  radius: '70%',
  amplitude: 8,             // 波浪振幅
  waveLength: '80%',
  phase: 0,
  period: 3000,             // 动画周期（ms）
  color: ['#3293fb'],
  backgroundStyle: {
    color: '#f0f2f5'
  },
  outline: {
    show: true,
    borderDistance: 4,
    itemStyle: {
      borderColor: '#3293fb',
      borderWidth: 2
    }
  },
  label: {
    show: true,
    formatter: function(params) {
      return (params.value * 100).toFixed(0) + '%';
    },
    fontSize: 28,
    fontWeight: 600,
    color: '#3293fb'
  }
}],
labelLayout: { hideOverlap: true }
```

### 多波浪

```javascript
data: [0.68, 0.6, 0.55],   // 多层波浪
color: ['#3293fb', 'rgba(50,147,251,0.6)', 'rgba(50,147,251,0.3)']
```
