#!/usr/bin/env python3
"""
生产订单管理模块

提供生产订单查询、详情获取等功能。
"""

import logging

from ..exceptions import YonSuiteAPIError
from ..models import ProductionOrder, ProductionOrderDetail
from .base import BaseAPIClient, retry_on_failure

logger = logging.getLogger(__name__)


class ProductionModule(BaseAPIClient):
    """生产订单管理模块"""

    def __init__(self, gateway_url: str | None = None):
        super().__init__(gateway_url=gateway_url)
        self.base_path = "/yonbip/mfg/productionorder"

    @retry_on_failure()
    def query_orders(self, access_token: str, page_index: int = 1, page_size: int = 500) -> dict:
        """
        查询生产订单列表

        API: POST /yonbip/mfg/productionorder/list

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
            "simpleVOs": [],
            "queryOrders": [{"field": "vouchdate", "order": "desc"}],
        }

        logger.info(f"查询生产订单列表，页码：{page_index}，每页：{page_size}")
        result = self._http_post_raw(url, body)
        return self.check_response(result, "查询生产订单列表")

    @retry_on_failure()
    def get_order_detail(self, access_token: str, order_id: str) -> dict:
        """
        查询生产订单详情

        API: GET /yonbip/mfg/productionorder/detail

        Args:
            access_token: API 访问 Token
            order_id: 生产订单 ID

        Returns:
            API 响应结果
        """
        url = f"{self.gateway_url}{self.base_path}/detail"
        params = {"access_token": access_token, "id": order_id}

        logger.info(f"查询生产订单详情：id={order_id}")
        result = self._http_get(url, params)
        return self.check_response(result, "查询生产订单详情")

    def query_orders_parsed(self, access_token: str) -> list[ProductionOrder]:
        """
        查询生产订单列表（解析为模型对象）

        Args:
            access_token: API 访问 Token

        Returns:
            ProductionOrder 对象列表
        """
        result = self.query_orders(access_token)
        data = result.get("data", [])
        if isinstance(data, list):
            return [ProductionOrder.from_api(item) for item in data]
        return []

    def get_order_detail_parsed(self, access_token: str, order_id: str) -> ProductionOrderDetail | None:
        """
        查询生产订单详情（解析为模型对象）

        Args:
            access_token: API 访问 Token
            order_id: 生产订单 ID

        Returns:
            ProductionOrderDetail 对象，如果未找到则返回 None
        """
        result = self.get_order_detail(access_token, order_id)
        data = result.get("data")
        if data:
            return ProductionOrderDetail.from_api(data)
        return None

    def format_orders_list(self, orders: list[ProductionOrder]) -> str:
        """
        格式化生产订单列表为可读文本

        Args:
            orders: 订单列表

        Returns:
            格式化的文本
        """
        if not orders:
            return "🏭 未找到生产订单"

        lines = [f"🏭 找到 {len(orders)} 个生产订单："]
        lines.append("-" * 70)

        for i, order in enumerate(orders, 1):
            lines.append(f"\n【订单 {i}】")
            lines.append(order.format())

        return "\n".join(lines)

    def format_order_detail(self, order: ProductionOrderDetail) -> str:
        """
        格式化生产订单详情为可读文本

        Args:
            order: 生产订单详情对象

        Returns:
            格式化的文本
        """
        lines = [order.format()]

        # 显示工序信息
        if order.processes:
            lines.append(f"\n⚙️ 工序信息：{len(order.processes)} 道")
            for i, process in enumerate(order.processes, 1):
                lines.append(f"   工序{i}: {process.get('processName', 'N/A')} - {process.get('status', 'N/A')}")

        # 显示材料信息
        if order.materials:
            lines.append(f"\n📦 材料信息：{len(order.materials)} 项")
            for mat in order.materials[:5]:  # 只显示前 5 项
                lines.append(f"   - {mat.get('materialName', 'N/A')}: {mat.get('quantity', 0)} {mat.get('unit', '')}")
            if len(order.materials) > 5:
                lines.append(f"   ... 还有 {len(order.materials) - 5} 项")

        # 显示联副产品信息
        if order.by_products:
            lines.append(f"\n🔄 联副产品：{len(order.by_products)} 项")
            for bp in order.by_products:
                lines.append(f"   - {bp.get('productName', 'N/A')}: {bp.get('quantity', 0)}")

        return "\n".join(lines)

    @retry_on_failure()
    def query_production_orders_batch(
        self,
        access_token: str,
        order_ids,  # List[str] or string
        show_process: bool = False,
        show_material: bool = False,
        show_by_product: bool = False,
    ) -> dict:
        """
        批量查询生产订单详情

        ⭐ 新增功能：一次查询多个生产订单的完整信息

        API: POST /yonbip/mfg/productionorder/batchGet

        Args:
            access_token: API 访问 Token
            order_ids: 生产订单 ID 列表（最多 50 个）或逗号分隔的字符串
            show_process: 是否展示工序（默认 False）
            show_material: 是否展示材料（默认 False）
            show_by_product: 是否展示联副产品（默认 False）

        Returns:
            API 响应结果，包含多个生产订单的完整信息
        """
        import urllib.parse

        # 处理 order_ids 参数（支持列表或逗号分隔字符串）
        if isinstance(order_ids, str):
            order_ids = [id.strip() for id in order_ids.split(",") if id.strip()]

        if not order_ids:
            raise YonSuiteAPIError("生产订单 ID 列表不能为空", error_code="INVALID_PARAMS")

        if len(order_ids) > 50:
            logger.warning(f"生产订单 ID 数量超过 50，将分批查询：{len(order_ids)}个")

        url = f"{self.gateway_url}{self.base_path}/batchGet?access_token={urllib.parse.quote(access_token)}"

        body = {
            "ids": order_ids[:50],  # 限制单次最多 50 个
            "isShowProcess": 1 if show_process else 0,
            "isShowMaterial": show_material,
            "isShowByProduct": show_by_product,
        }

        logger.info(f"批量查询生产订单详情：共{len(order_ids)}个订单")
        result = self._http_post_raw(url, body)
        return self.check_response(result, "批量查询生产订单详情")

    def query_production_orders_batch_parsed(
        self,
        access_token: str,
        order_ids: list[str],
        show_process: bool = False,
        show_material: bool = False,
        show_by_product: bool = False,
    ) -> list[ProductionOrderDetail]:
        """
        批量查询生产订单详情（解析为模型对象）

        Args:
            access_token: API 访问 Token
            order_ids: 生产订单 ID 列表
            show_process: 是否展示工序（默认 False）
            show_material: 是否展示材料（默认 False）
            show_by_product: 是否展示联副产品（默认 False）

        Returns:
            ProductionOrderDetail 对象列表
        """
        result = self.query_production_orders_batch(
            access_token, order_ids, show_process, show_material, show_by_product
        )
        data = result.get("data", [])
        if isinstance(data, list):
            return [ProductionOrderDetail.from_api(item) for item in data]
        return []

    def format_production_orders_batch(self, orders: list[ProductionOrderDetail]) -> str:
        """
        格式化批量生产订单查询结果为可读文本

        Args:
            orders: 生产订单详情列表

        Returns:
            格式化的文本
        """
        if not orders:
            return "🏭 未找到生产订单记录"

        lines = [f"🏭 批量查询结果：共 {len(orders)} 个生产订单"]
        lines.append("=" * 70)

        for i, order in enumerate(orders, 1):
            lines.append(f"\n【订单 {i}/{len(orders)}】")
            lines.append(f"   订单号：{order.code}")
            lines.append(f"   状态：{order.status_text}")
            lines.append(f"   物料：{order.material_name} ({order.material_code})")
            lines.append(f"   计划数量：{order.planned_qty}")
            lines.append(f"   完工数量：{order.completed_qty}")
            lines.append(f"   开工日期：{order.start_date}")
            lines.append("-" * 50)

        return "\n".join(lines)
