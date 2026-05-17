

# yonsuite-skill

用友 YonSuite 系统业务数据查询技能库

## 概述

yonsuite-skill 是一个用于连接和查询用友 YonSuite 系统的 Python 技能库，支持销售订单、采购订单、生产订单、库存、客户、供应商、产品、组织架构、会计凭证、待办事项、CRM 商机等业务数据的查询和分析。

## 功能特性

- **销售管理**: 销售订单列表查询、订单详情查询、批量查询
- **采购管理**: 采购订单列表查询、订单详情查询
- **生产管理**: 生产订单列表查询、订单详情查询、批量查询（含工序、材料、联副产品）
- **库存管理**: 实时库存查询
- **客户管理**: 客户档案查询、客户详情批量查询
- **供应商管理**: 供应商列表查询、供应商详情查询、批量查询
- **产品管理**: 产品档案查询
- **组织架构**: 组织详情查询、组织单元查询
- **财务管理**: 会计账簿查询、会计凭证查询
- **待办中心**: 用户待办事项查询
- **CRM 商机**: 商机列表查询、商机状态筛选

## 环境要求

- Python 3.8+
- 依赖库见 `requirements.txt`

## 安装

```bash
pip install -r requirements.txt
```

## 配置

在项目根目录创建 `.env` 文件，配置以下参数：

```env
YONSUITE_APP_KEY=your_app_key
YONSUITE_APP_SECRET=your_app_secret
YONSUITE_TENANT_ID=your_tenant_id
YONSUITE_GATEWAY_URL=https://gateway.yonyou.com
```

或通过环境变量配置：

```bash
export YONSUITE_APP_KEY=your_app_key
export YONSUITE_APP_SECRET=your_app_secret
export YONSUITE_TENANT_ID=your_tenant_id
export YONSUITE_GATEWAY_URL=https://gateway.yonyou.com
```

## 快速开始

### 基础用法

```python
from ys_client import YonSuiteClient

# 初始化客户端（自动读取配置）
client = YonSuiteClient()

# 查询销售订单
orders = client.query_sale_orders(page_index=1, page_size=500)
print(orders)

# 查询采购订单
purchase_orders = client.query_purchase_orders(page_index=1, page_size=500)

# 查询库存
stock = client.query_current_stock(page_index=1, page_size=500)

# 查询客户
customers = client.query_customers(page_index=1, page_size=500)

# 查询供应商
vendors = client.query_vendors(page_index=1, page_size=500)

# 查询生产订单
production_orders = client.query_production_orders(page_index=1, page_size=500)
```

### 订单详情查询

```python
# 销售订单详情
order_detail = client.get_order_detail(order_id="订单ID")

# 采购订单详情
purchase_detail = client.get_purchase_order_detail(order_id="订单ID")

# 生产订单详情
production_detail = client.get_production_order_detail(order_id="订单ID")
```

### 批量查询

```python
# 客户详情批量查询
customer_list = [{"id": "customer_id1"}, {"id": "customer_id2"}]
customer_details = client.query_customer_details_batch(customer_list)

# 供应商批量查询
vendor_ids = ["vendor_id1", "vendor_id2"]
vendors = client.query_vendors_batch(client.cache.get("access_token"), vendor_ids)

# 生产订单批量查询（支持工序、材料、联副产品）
order_ids = ["order_id1", "order_id2"]
production_orders = client.query_production_orders_batch(
    order_ids,
    show_process=True,    # 包含工序
    show_material=True,   # 包含材料
    show_by_product=True  # 包含联副产品
)
```

### 待办查询

```python
# 查询用户待办
todos = client.query_user_todos(page_no=1, page_size=10)
todos_parsed = client.query_user_todos_parsed(page_no=1, page_size=10)

# 格式化输出
todo_info = client.format_todo_info(todos_parsed)
print(todo_info)
```

### CRM 商机查询

```python
# 查询商机列表
opportunities = client.query_opportunities(
    page_index=1,
    page_size=500,
    is_sum=True  # 汇总数据
)

# 查询进行中商机
opportunities = client.query_opportunities(
    oppt_state="0",  # 进行中
    is_sum=True
)

# 查询赢单商机
opportunities = client.query_opportunities(
    win_lose_state="0",  # 赢单
    is_sum=True
)
```

### 会计凭证查询

```python
# 查询账簿
accbooks = client.query_accbooks()

# 查询凭证
vouchers = client.query_vouchers(
    page_index=1,
    page_size=20,
    voucher_date_start="2024-01-01",
    voucher_date_end="2024-12-31"
)
```

## 数据模型

项目内置了完善的数据模型类：

- `SaleOrder` - 销售订单
- `SaleOrderDetail` - 销售订单详情
- `PurchaseOrder` - 采购订单
- `ProductionOrder` - 生产订单
- `ProductionOrderDetail` - 生产订单详情（含工序、材料）
- `Customer` - 客户
- `Vendor` / `VendorDetail` - 供应商
- `StockItem` - 库存
- `ProductItem` - 产品
- `TodoItem` - 待办
- `Opportunity` - 商机

## 查询脚本

项目提供了可直接运行的查询脚本：

```bash
# 查询销售订单并导出
python query_sale_orders_to_sheet.py

# 查询采购订单并导出
python query_purchase_orders_to_sheet.py

# 查询生产订单并导出
python query_production_orders_to_sheet.py

# 查询生产订单详情并导出
python query_production_orders_detail_to_sheet.py

# 查询库存并导出
python query_stock_to_sheet.py
```

## 错误处理

项目定义了丰富的异常类：

```python
from exceptions import (
    YonSuiteError,
    YonSuiteConfigError,
    YonSuiteAuthError,
    YonSuiteAPIError,
    YonSuiteNotFoundError,
    YonSuitePermissionError,
    YonSuiteRateLimitError,
    YonSuiteDataError,
    YonSuiteNetworkError,
    YonSuiteCacheError
)

try:
    orders = client.query_sale_orders()
except YonSuiteAuthError as e:
    print(f"认证失败: {e}")
except YonSuiteAPIError as e:
    print(f"API错误: {e}, 错误码: {e.error_code}")
except YonSuiteRateLimitError as e:
    print(f"频率限制, 重试等待: {e.retry_after}秒")
```

## 字段文档

详细字段说明请参考：

- `docs/sale_order_list_fields.md` - 销售订单字段
- `docs/purchase_order_list_fields.md` - 采购订单字段
- `docs/production_order_detail_fields.md` - 生产订单详情字段

## 示例代码

更多用法请参考 `examples/` 目录：

- `basic_usage.py` - 基础用法示例
- `advanced_usage.py` - 高级用法示例
- `new_features_demo.py` - 新功能演示

## 注意事项

1. **Token 缓存**: 默认启用 Token 缓存，缓存有效期由服务器返回的 `expire_in` 决定
2. **日期过滤**: 查询时需注意日期格式，格式为 `YYYY-MM-DD`
3. **主子表结构**: 订单类数据采用主子表结构，详情查询可获取子表（物料行）信息
4. **批量查询**: 批量查询可显著提升效率，建议大数据量时使用

## 许可证

MIT License

## 更新日志

详见 `CHANGELOG.md`