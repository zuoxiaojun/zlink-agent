# 桑基图（Sankey）

> 展示流量/资源的流向关系

```javascript
series: [{
  type: 'sankey',
  data: [
    { name: '直接访问' },
    { name: '邮件营销' },
    { name: '联盟广告' },
    { name: '视频广告' },
    { name: '搜索引擎' },
    { name: '百度' },
    { name: '谷歌' },
    { name: '必应' }
  ],
  links: [
    { source: '直接访问', target: '百度', value: 100 },
    { source: '邮件营销', target: '百度', value: 60 },
    { source: '邮件营销', target: '谷歌', value: 40 },
    { source: '联盟广告', target: '必应', value: 80 },
    { source: '视频广告', target: '百度', value: 70 },
    { source: '搜索引擎', target: '谷歌', value: 120 },
    { source: '搜索引擎', target: '必应', value: 50 }
  ],
  emphasis: { focus: 'adjacency' },
  nodeAlign: 'justify',
  lineStyle: { color: 'gradient', curveness: 0.5 },
  label: { fontSize: 12 }
}],
labelLayout: { hideOverlap: true }
```
