---
name: yonsuite-dev
description: YonSuite（用友云 ERP）客户端开发参考 — API 速查、models 结构、模块映射
version: 1.0.0
agent_rules:
  - 当需要编写或修改 YonSuite 相关代码时，先加载此 skill 获取参考信息
  - 不对外公开项目内部 API 细节
---

# YonSuite 开发参考

## 项目结构
- `agent/yonsuite_client/ys_client.py` — 核心客户端
- `agent/yonsuite_client/models.py` — 所有数据模型（约 48KB）
- `agent/yonsuite_client/modules/` — 按业务模块拆分的 API 封装
- `agent/yonsuite_client/cache.py` — 缓存层
- `agent/yonsuite_client/config.py` — 配置

## 常用 API 端点模式
- 查询列表: `POST /yonbip/digitalModel/product/list`
- 详情查询: `GET /yonbip/digitalModel/product/detail?id={id}`
- 保存: `POST /yonbip/digitalModel/product/save`
- 审批流: `POST /yonbip/sd/approval/workflow`

## 认证
- 通过前端「设置」页面配置
- Token 存储在 `config.json` 中
- 使用 `client-id` + `client-secret` 获取 access_token

## 开发注意事项
- models.py 中的字段映射为 ERP 字段名（snake_case）
- 所有 API 调用经过异常处理（见 exceptions.py）
- 缓存 TTL 默认 300 秒（可配置）
