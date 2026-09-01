---
name: "china-hotdata"
description: "中国实时热点数据采集工具。当用户询问热搜、热榜、热点、排行榜、榜单、票房、收视率、音乐排行、歌曲排名、报纸、新闻头条、人民日报等话题时使用此技能。覆盖：抖音/微博/百度/B站/快手热搜，QQ音乐/网易云/酷狗/酷我音乐榜，猫眼电影票房/电视剧收视/综艺热度，App Store游戏/应用排行榜，人民日报电子版PDF及高清版面图。通过 Node.js 脚本实时获取数据，JSON 格式输出，无需 API Key，无需服务器。"
---

# 中国实时热点数据采集工具

实时获取中国各大平台热点数据的 OpenClaw Skill。通过运行 Node.js 脚本获取最新数据，JSON 格式输出。

## 何时使用此技能

**当用户的问题涉及以下任意话题时，你应该使用此技能：**

### 热搜/热点类
用户提到：热搜、热榜、热门、热点、趋势、什么最火、大家在搜什么、今天发生了什么、吃瓜、全网热议、抖音、微博、百度、B站、哔哩哔哩、快手

→ 使用 `crawl-hot.js`

### 音乐/歌曲类
用户提到：音乐、歌曲、歌、热歌、新歌、飙升、排行榜、榜单、什么歌好听、现在流行什么歌、QQ音乐、网易云、酷狗、酷我

→ 使用 `crawl-music.js`

### 影视/娱乐/游戏类
用户提到：电影、票房、电视剧、网剧、综艺、收视率、热度、游戏排行、App Store、应用排行、好看的剧、最近上映、猫眼

→ 使用 `crawl-entertainment.js`

### 报纸/新闻类
用户提到：报纸、人民日报、看报、今日新闻头条、头版头条、要闻、日报

→ 使用 `crawl-paper.js`

## 使用方式

所有脚本通过 `node` 命令运行，输出 JSON 到标准输出。需要 Node.js 18+（内置 fetch）。

**重要：运行脚本时，工作目录必须在本技能的根目录下，即脚本路径相对于技能安装目录。**

### 快速选择指南

根据用户意图，选择对应命令：

| 用户想了解的内容 | 运行命令 |
|----------------|---------|
| 某平台热搜 | `node agent/skills/china-hotdata/scripts/crawl-hot.js --platform=平台名` |
| 所有平台热搜 | `node agent/skills/china-hotdata/scripts/crawl-hot.js` |
| 某平台音乐榜 | `node agent/skills/china-hotdata/scripts/crawl-music.js --platform=平台名 --type=hot或rising` |
| 所有音乐榜 | `node agent/skills/china-hotdata/scripts/crawl-music.js` |
| 电影票房/电视剧/综艺/游戏等 | `node agent/skills/china-hotdata/scripts/crawl-entertainment.js --type=类型` |
| 所有影视游戏数据 | `node agent/skills/china-hotdata/scripts/crawl-entertainment.js` |
| 今日/指定日期报纸 | `node agent/skills/china-hotdata/scripts/crawl-paper.js --date=日期` |

### 🔥 获取热搜数据

采集抖音、微博、百度、B站、快手五大平台的实时热搜榜单。

```bash
node agent/skills/china-hotdata/scripts/crawl-hot.js --platform=douyin
node agent/skills/china-hotdata/scripts/crawl-hot.js --platform=weibo
node agent/skills/china-hotdata/scripts/crawl-hot.js --platform=baidu
node agent/skills/china-hotdata/scripts/crawl-hot.js --platform=bilibili
node agent/skills/china-hotdata/scripts/crawl-hot.js --platform=kuaishou
node agent/skills/china-hotdata/scripts/crawl-hot.js
```

### 🎵 获取音乐排行榜

```bash
node agent/skills/china-hotdata/scripts/crawl-music.js --platform=qq --type=hot
node agent/skills/china-hotdata/scripts/crawl-music.js --platform=wangyi --type=rising
node agent/skills/china-hotdata/scripts/crawl-music.js
```

### 🎬 获取影视/游戏数据

```bash
node agent/skills/china-hotdata/scripts/crawl-entertainment.js --type=movie
node agent/skills/china-hotdata/scripts/crawl-entertainment.js --type=tv
node agent/skills/china-hotdata/scripts/crawl-entertainment.js --type=variety
node agent/skills/china-hotdata/scripts/crawl-entertainment.js --type=game_free
node agent/skills/china-hotdata/scripts/crawl-entertainment.js
```

### 📰 获取人民日报电子版

```bash
node agent/skills/china-hotdata/scripts/crawl-paper.js
node agent/skills/china-hotdata/scripts/crawl-paper.js --date=yesterday
node agent/skills/china-hotdata/scripts/crawl-paper.js --date=2026-03-10
```

## 输出格式

所有脚本统一输出 JSON：

```json
{
  "status": "ok",
  "results": {
    "平台名": {
      "success": true,
      "data": { "sj": [...], "time": "2026-01-01 12:00:00" },
      "count": 50
    }
  }
}
```

### 热搜数据字段
| word | 热搜关键词 |
| hot_value | 热度值 |
| url | 搜索链接 |
| label | 标签（热/新等） |

### 音乐数据字段
| name | 歌曲名 |
| geshou | 歌手 |
| hot | 排名/热度 |

### 影视数据字段
电影：name（片名）、piaofang（票房）
电视剧/网播/综艺：name（名称）、piaofang（收视率/热度）
App Store：name（应用名）、pingfen（评分）

### 报纸数据字段
| page | 版面编号 |
| title | 版面标题 |
| pdf_url | PDF 下载链接 |
| image_url | 版面高清大图链接 |

## 注意事项
1. 需要 Node.js 18+ 版本
2. 所有数据实时获取，响应时间通常 1-3 秒
3. 无需任何 API Key 或密钥配置