# 生产订单分析报告 — 踩坑实录（2026-04-30）

## 本次教训

**错误：跳过 data-analysis + 自写 HTML**

本次生成生产订单周报时，三处违规：

1. **没调用 `data-analysis` 技能** — 直接上结论，没跑 HHI/IQR/漏斗分析，被用户指出"没有数据分析"
2. **没用模板** — 自己写了蓝底 Hero 的 HTML，没用 `sale_analysis_template.html`（用友红 #E60012 系），样式全错
3. **明细表截断** — 25 条数据只放了 10 条，被指出"订单明细也没有"

**正确流程（强制）：**
```
① 查数据（YonSuite API）
② skill_view('data-analysis') + 执行统计分析（HHI/IQR/漏斗）
③ 生成图表（mcp-server-chart）
④ 用 sale_analysis_template.html 组装 HTML（含决策简报+全量明细）
⑤ 直调 OpenAPI 发飞书（不走 open）
```

## 生产订单特有字段注意

| 字段 | 含义 |
|------|------|
| `status` | 0=开立,1=已审核,2=已关闭,3=审核中,4=已锁定,5=生产完工 |
| `OrderProduct_stockStatus` | 0=未入库,1=部分入库,2=全部入库 |
| `OrderProduct_materialStatus` | 0=未领料,1=部分领料,2=已领料 |
| `OrderProduct_completedQuantity` | 已完工数量（不是入库数量） |
| `OrderProduct_incomingQuantity` | 入库数量（入库状态用 stockStatus） |

## 生产订单分析核心指标

```
HHI 集中度：sum(产品占比²)，>0.4 为极高集中
完工率：sum(completedQuantity) / sum(quantity)
入库率：已入库产量 / 总产量（含未完工但已入库部分）
漏斗：按 status 分组统计行数和产量
```

## 模板现状（2026-04-30 更新）

- `templates/sale_analysis_template.html` — 销售/采购分析通用（红 #E60012 系）
- `templates/production_analysis_template.html` — **生产订单分析专用**（2026-04-30 从实战模板固化，含生产状态标签 + stock-tag）
- `templates/sale_order_detail_template.html` — 订单明细专用

## 状态标签对应

```html
<span class="status-tag s-closed">已关闭</span>      <!-- status=2, 绿色 -->
<span class="status-tag s-locked">已锁定</span>      <!-- status=4, 灰色 -->
<span class="status-tag s-finished">生产完工</span>   <!-- status=5, 橙色 -->
<span class="status-tag s-approved">已审核</span>    <!-- status=1, 蓝色 -->
```

## 文件发送

生产订单报告生成后，在飞书会话中 → 直调 OpenAPI `file_type="stream"` 发文件，不走 `send_message` 工具（websocket 限制），也不发云盘链接。

```python
# 正确方式
upload = requests.post(
    'https://open.feishu.cn/open-apis/im/v1/files?receive_id_type=open_id',
    headers={'Authorization': f'Bearer {tat}'},
    data={'file_name': fname, 'file_type': 'stream', 'receive_id': OPEN_ID},
    files={'file': (fname, f.read(), 'application/octet-stream')}
)
uk = upload.json()['data']['file_key']
requests.post('.../messages?receive_id_type=open_id',
    json={'receive_id': OPEN_ID, 'msg_type': 'file', 'content': json.dumps({'file_key': uk})})
```
