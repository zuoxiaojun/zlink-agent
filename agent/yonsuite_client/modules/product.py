#!/usr/bin/env python3
"""
物料档案查询模块

提供物料（产品）主数据的分页查询功能。
API: POST /yonbip/digitalModel/product/queryByPage
"""

import logging
from typing import Any

from ..models import ProductItem
from .base import BaseAPIClient, retry_on_failure

logger = logging.getLogger(__name__)


class ProductModule(BaseAPIClient):
    """物料档案查询模块"""

    def __init__(self, gateway_url: str = None):
        super().__init__(gateway_url=gateway_url)
        self.base_path = "/yonbip/digitalModel/product"

    @retry_on_failure()
    def query_products(
        self,
        access_token: str,
        product_code: str = "",
        product_name: str = "",
        page_index: int = 1,
        page_size: int = 10,
        stop_status: bool = False,
        **kwargs,
    ) -> dict:
        """
        分页查询物料档案

        API: POST /yonbip/digitalModel/product/integration/querylist

        Args:
            access_token: API 访问 Token
            product_code: 物料编码（可选，精确匹配）
            product_name: 物料名称（可选，模糊匹配）
            page_index: 页码（默认1）
            page_size: 每页条数（默认10）
            stop_status: 停用状态，默认 false=启用
            **kwargs: 其他过滤参数（managerClassCodeList, productClassCodeList 等）

        Returns:
            API 响应结果，含 recordList、recordCount、pageCount 等
        """
        import urllib.parse

        url = (
            f"{self.gateway_url}{self.base_path}/integration/querylist?access_token={urllib.parse.quote(access_token)}"
        )

        payload = {
            "pageIndex": page_index,
            "pageSize": page_size,
            "stopStatus": stop_status,
        }

        # 物料编码（精确匹配，传入数组）
        if product_code:
            payload["productCodeList"] = [product_code]

        # 物料名称（模糊匹配，传入数组）
        if product_name:
            payload["productNameList"] = [product_name]

        # 其他可选过滤参数
        for key, value in kwargs.items():
            if value and key in [
                "managerClassIdList",
                "managerClassCodeList",
                "productClassIdList",
                "productClassCodeList",
                "purchaseClassIdList",
                "purchaseClassCodeList",
                "productTemplate",
                "modelDescription",
                "model",
                "beginTime",
                "endTime",
            ]:
                payload[key] = value if isinstance(value, list) else [value]

        logger.info(f"查询物料档案：code={product_code}, name={product_name}, page={page_index}")
        result = self._http_post_raw(url, payload)
        return self.check_response(result, "查询物料档案")

    def query_products_parsed(
        self,
        access_token: str,
        product_code: str = "",
        product_name: str = "",
        page_index: int = 1,
        page_size: int = 10,
        stop_status: bool = False,
        **kwargs,
    ) -> dict[str, Any]:
        """
        查询物料档案（解析为模型对象 + 分页信息）

        Args:
            access_token: API 访问 Token
            **kwargs: 查询参数（同 query_products）

        Returns:
            包含 items列表、total、pageCount、pageIndex 的字典
        """
        result = self.query_products(
            access_token,
            product_code=product_code,
            product_name=product_name,
            page_index=page_index,
            page_size=page_size,
            stop_status=stop_status,
            **kwargs,
        )

        data = result.get("data", {})

        items = []
        for item in data.get("recordList", []):
            items.append(ProductItem.from_api(item))

        return {
            "items": items,
            "total": int(data.get("recordCount", 0)),
            "page_count": int(data.get("pageCount", 0)),
            "page_index": int(data.get("pageIndex", page_index)),
            "page_size": int(data.get("pageSize", page_size)),
            "have_next_page": data.get("haveNextPage", False),
        }

    def format_product_info(self, products: list[ProductItem]) -> str:
        """
        格式化物料信息为可读文本

        Args:
            products: 物料项目列表

        Returns:
            格式化的文本
        """
        if not products:
            return "📦 未找到物料记录"

        lines = [f"📦 物料记录：{len(products)} 条"]
        lines.append("-" * 70)

        for i, p in enumerate(products, 1):
            lines.append(f"\n【物料 {i}】")
            lines.append(p.format())

        return "\n".join(lines)
