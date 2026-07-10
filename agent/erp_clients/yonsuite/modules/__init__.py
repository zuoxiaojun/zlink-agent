#!/usr/bin/env python3
"""
YonSuite 功能模块包

各模块说明：
- base: 基础 HTTP 客户端和工具
- sales: 销售订单管理
- purchase: 采购订单管理
- stock: 库存查询
- customer: 客户档案管理
- vendor: 供应商档案管理
- production: 生产订单管理
- todo: 用户待办查询
- voucher: 凭证列表查询
- crm: 商机管理
"""

from .base import BaseAPIClient
from .crm import CrmModule
from .customer import CustomerModule
from .production import ProductionModule
from .purchase import PurchaseModule
from .sales import SalesModule
from .stock import StockModule
from .todo import TodoItem, TodoModule
from .vendor import VendorModule
from .voucher import VoucherModule

__all__ = [
    "BaseAPIClient",
    "SalesModule",
    "PurchaseModule",
    "StockModule",
    "CustomerModule",
    "VendorModule",
    "ProductionModule",
    "TodoModule",
    "TodoItem",
    "VoucherModule",
    "CrmModule",
]
