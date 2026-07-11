#!/usr/bin/env python3
"""
库存查询模块

提供现存量、可用量等库存查询功能。
"""

import logging
from typing import Any

from ..models import StockItem
from .base import BaseAPIClient, retry_on_failure

logger = logging.getLogger(__name__)


class StockModule(BaseAPIClient):
    """库存查询模块"""

    def __init__(self, gateway_url: str | None = None):
        super().__init__(gateway_url=gateway_url)
        self.base_path = "/yonbip/scm/stock"

    @retry_on_failure()
    def query_current_stock(
        self, access_token: str, page_index: int = 1, page_size: int = 500, product: Any = None
    ) -> dict:
        """
        查询现存量

        API: POST /yonbip/scm/stock/QueryCurrentStocksByCondition

        Args:
            access_token: API 访问 Token
            page_index: 页码，默认值：1
            page_size: 每页行数，默认值：500
            product: 物料ID，支持单个字符串或列表批量，如 "1921567765125888" 或 ["1921567765125888", "1921567765125889"]

        Returns:
            API 响应结果
        """
        import urllib.parse

        # access_token 放在 URL 参数中（YonSuite API 要求）
        url = f"{self.gateway_url}{self.base_path}/QueryCurrentStocksByCondition?access_token={urllib.parse.quote(access_token)}"

        # 构建查询条件，包含必填的分页参数
        payload = {"pageIndex": page_index, "pageSize": page_size}

        # 如果有物料ID过滤，加到查询条件中
        if product is not None:
            payload["product"] = product

        logger.info(f"查询库存现存量，页码：{page_index}，每页：{page_size}，物料ID：{product}")
        # 使用 _http_post_raw，因为 URL 已包含 access_token
        result = self._http_post_raw(url, payload)
        return self.check_response(result, "查询库存现存量")

    def query_stock_parsed(self, access_token: str) -> list[StockItem]:
        """
        查询现存量（解析为模型对象）

        Args:
            access_token: API 访问 Token

        Returns:
            StockItem 对象列表
        """
        result = self.query_current_stock(access_token)
        data = result.get("data", [])
        if isinstance(data, list):
            return [StockItem.from_api(item) for item in data]
        return []

    def format_stock_info(self, stock_items: list[StockItem]) -> str:
        """
        格式化库存信息为可读文本

        Args:
            stock_items: 库存项目列表

        Returns:
            格式化的文本
        """
        if not stock_items:
            return "📦 未找到库存记录"

        lines = [f"📦 库存记录：{len(stock_items)} 条"]
        lines.append("-" * 70)

        for i, item in enumerate(stock_items, 1):
            lines.append(f"\n【库存 {i}】")
            lines.append(item.format())

        return "\n".join(lines)
