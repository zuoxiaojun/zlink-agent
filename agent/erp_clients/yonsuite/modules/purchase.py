#!/usr/bin/env python3
"""
采购订单管理模块

提供采购订单查询等功能。
"""

import logging

from ..models import PurchaseOrder
from .base import BaseAPIClient, retry_on_failure

logger = logging.getLogger(__name__)


class PurchaseModule(BaseAPIClient):
    """采购订单管理模块"""

    def __init__(self, gateway_url: str | None = None):
        super().__init__(gateway_url=gateway_url)
        self.base_path = "/yonbip/scm/purchaseorder"

    @retry_on_failure()
    def query_orders(self, access_token: str, page_index: int = 1, page_size: int = 500) -> dict:
        """
        查询采购订单列表

        API: POST /yonbip/scm/purchaseorder/list

        Args:
            access_token: API 访问 Token
            page_index: 页码，默认值：1
            page_size: 每页行数，默认值：500

        Returns:
            API 响应结果
        """
        import urllib.parse

        # access_token 放在 URL 参数中（YonSuite API 要求）
        url = f"{self.gateway_url}{self.base_path}/list?access_token={urllib.parse.quote(access_token)}"

        # body 中不包含 access_token，只保留必填参数
        body = {
            "pageIndex": page_index,
            "pageSize": page_size,
            "isSum": False,
            "simpleVOs": [],
            "queryOrders": [{"field": "vouchdate", "order": "desc"}],
        }

        logger.info(f"查询采购订单列表，页码：{page_index}，每页：{page_size}")
        result = self._http_post_raw(url, body)
        return self.check_response(result, "查询采购订单列表")

    def query_orders_parsed(self, access_token: str) -> list[PurchaseOrder]:
        """
        查询采购订单列表（解析为模型对象）

        Args:
            access_token: API 访问 Token

        Returns:
            PurchaseOrder 对象列表
        """
        result = self.query_orders(access_token)
        data = result.get("data", [])
        if isinstance(data, list):
            return [PurchaseOrder.from_api(item) for item in data]
        return []

    def format_orders_list(self, orders: list[PurchaseOrder]) -> str:
        """
        格式化采购订单列表为可读文本

        Args:
            orders: 订单列表

        Returns:
            格式化的文本
        """
        if not orders:
            return "未找到采购订单"

        lines = [f"🛒 找到 {len(orders)} 个采购订单："]
        lines.append("-" * 70)

        for i, order in enumerate(orders, 1):
            lines.append(f"\n【订单 {i}】")
            lines.append(f"   订单编号：{order.code}")
            lines.append(f"   订单 ID: {order.id}")
            lines.append(f"   供应商：{order.supplier_name}")  # type: ignore[attr-defined]
            lines.append(f"   订单金额：¥{order.amount:,.2f}")  # type: ignore[attr-defined]
            lines.append(f"   状态：{order.status}")
            lines.append(f"   单据日期：{order.vouchdate}")

        return "\n".join(lines)

    @retry_on_failure()
    def get_order_detail(self, access_token: str, order_id: str) -> dict:
        """
        查询采购订单详情

        API: GET /yonbip/scm/purchaseorder/detail

        Args:
            access_token: API 访问 Token
            order_id: 采购订单 ID（必填）

        Returns:
            API 响应结果，包含完整的采购订单信息：
            - 表头信息：订单编号、供应商、采购组织、交易类型、单据日期等
            - 金额信息：含税金额、无税金额、税额、本币金额等
            - 状态信息：单据状态、审核状态、变更状态等
            - 子表信息：采购订单明细行（purchaseOrders）
            - 付款计划：付款计划子表（paymentSchedules）
            - 付款执行：付款执行明细（paymentExeDetail）
        """
        import urllib.parse

        # GET 请求，参数放在 URL 中
        url = f"{self.gateway_url}{self.base_path}/detail?access_token={urllib.parse.quote(access_token)}&id={order_id}"

        logger.info(f"查询采购订单详情：order_id={order_id}")
        result = self._http_get(url)
        return self.check_response(result, "查询采购订单详情")

    def format_order_detail(self, detail: dict) -> str:
        """
        格式化采购订单详情为可读文本

        Args:
            detail: 采购订单详情字典（API 返回的 data 字段）

        Returns:
            格式化的文本字符串
        """
        if not detail:
            return "未找到采购订单信息"

        lines = []

        # 基本信息
        lines.append("🛒 采购订单基本信息")
        lines.append(f"  订单 ID: {detail.get('id', 'N/A')}")
        lines.append(f"  订单编号：{detail.get('code', 'N/A')}")
        lines.append(f"  交易类型：{detail.get('bustype_name', 'N/A')}")
        lines.append(f"  采购组织：{detail.get('org_name', 'N/A')}")
        lines.append(f"  采购部门：{detail.get('department_name', 'N/A')}")
        lines.append(f"  采购员：{detail.get('operator_name', 'N/A')}")
        lines.append(f"  单据日期：{detail.get('vouchdate', 'N/A')}")
        lines.append(f"  希望到货日期：{detail.get('expectDate', 'N/A')}")

        # 供应商信息
        lines.append("\n🏭 供应商信息")
        lines.append(f"  供应商名称：{detail.get('vendor_name', 'N/A')}")
        lines.append(f"  供应商编码：{detail.get('vendor_code', 'N/A')}")
        lines.append(f"  供方联系人：{detail.get('contact', 'N/A')}")
        lines.append(f"  联系人手机：{detail.get('contactTel', 'N/A')}")

        # 金额信息
        lines.append("\n💰 金额信息")
        lines.append(f"  含税金额：¥{detail.get('oriSum', 0):,.2f}")
        lines.append(f"  无税金额：¥{detail.get('oriMoney', 0):,.2f}")
        lines.append(f"  税额：¥{detail.get('oriTax', 0):,.2f}")
        lines.append(f"  本币含税金额：¥{detail.get('natSum', 0):,.2f}")
        lines.append(f"  币种：{detail.get('currency_name', 'N/A')}")
        lines.append(f"  汇率：{detail.get('exchRate', 1)}")

        # 状态信息
        lines.append("\n📊 状态信息")
        status_map = {"0": "开立", "1": "已审核", "2": "已关闭", "3": "审核中"}
        bizstatus_map = {"0": "未提交", "1": "已提交", "2": "已关闭", "3": "待入库", "4": "已完成"}
        lines.append(f"  单据状态：{bizstatus_map.get(detail.get('bizstatus'), detail.get('bizstatus', 'N/A'))}")  # type: ignore[arg-type]
        lines.append(f"  审核状态：{status_map.get(detail.get('status'), detail.get('status', 'N/A'))}")  # type: ignore[arg-type]
        lines.append(f"  变更状态：{detail.get('modifyStatus', 'N/A')}")
        lines.append(f"  审核人：{detail.get('auditor', 'N/A')}")
        lines.append(f"  审核时间：{detail.get('auditTime', 'N/A')}")

        # 累计执行情况
        lines.append("\n📦 执行情况")
        lines.append(f"  累计到货金额：¥{detail.get('allTotalArrivedTaxMoney', 0):,.2f}")
        lines.append(f"  累计入库金额：¥{detail.get('allTotalInTaxMoney', 0):,.2f}")
        lines.append(f"  累计开票金额：¥{detail.get('allTotalInvoiceMoney', 0):,.2f}")
        lines.append(f"  累计付款金额：¥{detail.get('totalPayMoney', 0):,.2f}")

        # 订单明细
        purchase_orders = detail.get("purchaseOrders", [])
        if purchase_orders:
            lines.append(f"\n📋 订单明细（共{len(purchase_orders)}行）")
            for i, item in enumerate(purchase_orders[:5], 1):  # 只显示前 5 行
                lines.append(f"  {i}. {item.get('product_cName', 'N/A')} ({item.get('product_model', 'N/A')})")
                lines.append(f"     数量：{item.get('qty', 0)} {item.get('unit_name', 'N/A')}")
                lines.append(f"     单价：¥{item.get('oriUnitPrice', 0):,.2f}")
                lines.append(f"     金额：¥{item.get('oriSum', 0):,.2f}")
                lines.append(f"     到货状态：{item.get('arrivedStatus', 'N/A')}")
                lines.append(f"     入库状态：{item.get('inWHStatus', 'N/A')}")

        # 付款计划
        payment_schedules = detail.get("paymentSchedules", [])
        if payment_schedules:
            lines.append(f"\n💳 付款计划（共{len(payment_schedules)}期）")
            for i, schedule in enumerate(payment_schedules[:3], 1):
                lines.append(f"  {i}. {schedule.get('name', 'N/A')} - {schedule.get('payRatio', 0)}%")
                lines.append(f"     金额：¥{schedule.get('amount', 0):,.2f}")
                lines.append(f"     付款日期：{schedule.get('startDateTime', 'N/A')}")

        return "\n".join(lines)
