# 销售分析报告 — HTML表格从JSON程序化生成

> **规则（强制）：分析报告的订单明细表格必须从 `sale_order_result.json` 程序化生成，绝不能手动录入。**
> 手动录入会产生数据错误（如客户名、金额错位），且无法规模化。

## 完整执行流程

```python
import json, math

with open("data/sale_order_result.json") as f:
    d = json.load(f)

headers = d["headers"]
rows = d["data"]

# 字段索引
idx_code = headers.index("单据编号")
idx_date = headers.index("单据日期")
idx_customer = headers.index("客户")
idx_dept = headers.index("销售部门")
idx_salesman = headers.index("销售业务员")
idx_status = headers.index("订单状态")
idx_amount = headers.index("含税金额")
idx_product = headers.index("物料名称")

# 过滤合计行
data_rows = [r for r in rows if r[idx_code] != "合计"]

# 按单据号去重（主表级）
orders = {}
for r in data_rows:
    code = r[idx_code]
    if code not in orders:
        orders[code] = {
            "date": r[idx_date],
            "customer": r[idx_customer],
            "dept": r[idx_dept] or "",
            "salesman": r[idx_salesman] or "",
            "status": r[idx_status],
            "amount": 0.0,
            "products": [],
        }
    orders[code]["amount"] += float(r[idx_amount] or 0)
    orders[code]["products"].append(r[idx_product])

# 状态 tag CSS class 映射
STATUS_CLASS = {
    "DELIVERGOODS": "s-DELIVERGOODS",
    "TAKEDELIVERY": "s-TAKEDELIVERY",
    "ENDORDER": "s-ENDORDER",
    "CONFIRMORDER": "s-CONFIRMORDER",
    "OPPOSE": "s-OPPOSE",
}
STATUS_LABEL = {
    "DELIVERGOODS": "待发货",
    "TAKEDELIVERY": "待收货",
    "ENDORDER": "已完成",
    "CONFIRMORDER": "开立",
    "OPPOSE": "已取消",
}


# 程序化生成HTML表格行
def fmt_amount(v):
    if v >= 1e8:
        return f"¥{v / 1e8:.2f}亿"
    if v >= 1e4:
        return f"¥{v / 1e4:.2f}万"
    return f"¥{v:,.0f}"


rows_html = []
for code in sorted(orders.keys(), key=lambda c: orders[c]["date"]):
    o = orders[code]
    status_cls = STATUS_CLASS.get(o["status"], "")
    status_lbl = STATUS_LABEL.get(o["status"], o["status"])
    rows_html.append(f"""<tr>
  <td>{code}</td>
  <td>{o["date"]}</td>
  <td class="customer">{o["customer"]}</td>
  <td>{o["dept"]}</td>
  <td>{o["salesman"]}</td>
  <td class="status-tag {status_cls}">{status_lbl}</td>
  <td class="amount">{fmt_amount(o["amount"])}</td>
  <td>{" / ".join(o["products"])}</td>
</tr>""")

table_body = "\n".join(rows_html)
print(table_body)  # 粘贴到HTML模板的 <tbody> 中
```

## 关键要点

1. **不要手动输入任何数据** — 金额、客户名、产品名全部从JSON读取
2. **`orders` 字典按 `code` 去重** — 同一订单多行物料只显示一行汇总
3. **空值兜底** — `r[idx_dept] or ''` 避免 null 显示为 "None"
4. **`fmt_amount()` 大金额换算** — ≥1亿显示"X.XX亿"，≥1万显示"X.X万"
5. **状态映射** — `nextStatus` 是英文代码，显示时必须映射为中文标签

## 常见错误

| 错误 | 后果 |
|------|------|
| 手动录入客户名/金额 | 数据错误，无法被发现 |
| 空值未做 `or ''` 处理 | HTML显示 "None" |
| 大金额直接显示不做换算 | 金额过长破坏布局 |
| 状态代码未映射直接显示英文 | 用户看不懂 |
