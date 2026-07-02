---
name: weather
description: 查询天气、风速、空气质量（AQI）和紫外线（UV）指数，附带数据来源链接
---

# Weather Skill

当用户通过 `/weather <地点>` 查询天气时，按以下流程执行。

支持格式示例：`/weather 北京`、`/weather 东京`、`/weather New York`

## 执行步骤

### 步骤 1：解析地点

从用户输入中提取地点名称。如果用户未提供地点，使用 WebSearch 搜索 "my ip location" 获取用户所在城市，或询问用户。

### 步骤 2：地理编码

使用 Open-Meteo Geocoding API（免费，无需 API 密钥）将地点转为坐标：

```
https://geocoding-api.open-meteo.com/v1/search?name={URL_ENCODED_CITY}&count=1&language=zh&format=json
```

解析返回结果中的 `latitude`、`longitude`、`name`、`country`。如果未找到结果，告知用户并建议检查地点名称。

### 步骤 3：获取天气数据

使用 Open-Meteo 的四个 API 端点（均免费，无需 API 密钥）：

**天气与风速：** `https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,wind_direction_10m&timezone=auto`

**紫外线指数：** `https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=uv_index&timezone=auto`

**空气质量：** `https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=european_aqi,us_aqi,pm2_5,pm10,ozone,nitrogen_dioxide,sulphur_dioxide,carbon_monoxide`

### 步骤 4：格式化输出

用中文输出，按以下结构清晰展示：

**地点与时间：** 城市名、国家、当地时间

**天气概况：** 根据 WMO Weather Code 翻译天气状况（见下方映射表），当前温度、体感温度、湿度

**风速风向：** 风速（km/h），风向（中文方位，如东北风、西南风）

**紫外线指数：** UV 指数数值及等级（低/中等/高/很高/极高），附带防护建议

**空气质量：** 欧洲 AQI 或 US AQI 数值及等级（好/中等/对敏感人群不健康/不健康/非常不健康/危险），主要污染物（如有）

### 步骤 5：数据来源链接

在回答末尾附上：

- [Open-Meteo 天气数据](https://open-meteo.com/)
- [Open-Meteo 空气质量数据](https://open-meteo.com/en/docs/air-quality-api)
- [Open-Meteo 紫外线数据](https://open-meteo.com/en/docs)

---

## 参考数据

### WMO Weather Code 中文映射

| Code | 天气状况 |
|------|----------|
| 0 | 晴天 |
| 1 | 大部晴朗 |
| 2 | 局部多云 |
| 3 | 多云 |
| 45 | 雾 |
| 48 | 沉积雾凇 |
| 51 | 小毛毛雨 |
| 53 | 中毛毛雨 |
| 55 | 大毛毛雨 |
| 56 | 冻毛毛雨（轻） |
| 57 | 冻毛毛雨（重） |
| 61 | 小雨 |
| 63 | 中雨 |
| 65 | 大雨 |
| 66 | 冻雨（轻） |
| 67 | 冻雨（重） |
| 71 | 小雪 |
| 73 | 中雪 |
| 75 | 大雪 |
| 77 | 雪粒 |
| 80 | 小阵雨 |
| 81 | 中阵雨 |
| 82 | 大阵雨 |
| 85 | 小阵雪 |
| 86 | 大阵雪 |
| 95 | 雷暴 |
| 96 | 雷暴伴小冰雹 |
| 99 | 雷暴伴大冰雹 |

### 风向度数转中文方位

| 角度范围 | 风向 |
|----------|------|
| 0°-22.5°, 337.5°-360° | 北风 |
| 22.5°-67.5° | 东北风 |
| 67.5°-112.5° | 东风 |
| 112.5°-157.5° | 东南风 |
| 157.5°-202.5° | 南风 |
| 202.5°-247.5° | 西南风 |
| 247.5°-292.5° | 西风 |
| 292.5°-337.5° | 西北风 |

### UV 指数分级

| 指数范围 | 等级 | 防护建议 |
|----------|------|----------|
| 0-2 | 低 | 无特殊防护 |
| 3-5 | 中等 | 佩戴防晒用品 |
| 6-7 | 高 | 减少日晒，做好防护 |
| 8-10 | 很高 | 避免正午外出 |
| 11+ | 极高 | 尽量避免外出 |

### 欧洲 AQI 分级

| EAQI 范围 | 等级 |
|-----------|------|
| 0-20 | 好 |
| 20-40 | 一般 |
| 40-60 | 对敏感人群不健康 |
| 60-80 | 不健康 |
| 80-100 | 非常不健康 |
| 100+ | 危险 |

---

## 错误处理

- **API 请求失败：** 使用 WebSearch 搜索 "`{地点} 当前天气`" 和 "`{地点} 空气质量`" 作为备选方案
- **地点未找到：** 提示用户检查地点名称，建议尝试英文名称或更大范围的地点
- **部分数据缺失：** 展示已获取的数据，并在缺失项注明"暂无数据"
