#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
销售订单管理模块

提供销售订单查询、详情获取等功能。
"""

import logging
import urllib.parse
from typing import Optional, List, Dict, Any

from .base import BaseAPIClient, retry_on_failure
from ..config import config
from ..models import SaleOrder, SaleOrderDetail, APIResponse
from ..exceptions import YonSuiteAPIError

logger = logging.getLogger(__name__)


class SalesModule(BaseAPIClient):
    """销售订单管理模块"""
    
    def __init__(self, gateway_url: str = None):
        super().__init__(gateway_url=gateway_url)
        self.base_path = "/yonbip/sd/voucherorder"
    
    @retry_on_failure()
    def query_orders(self, access_token: str, page_index: int = 1, page_size: int = 500, isSum: bool = False,
                     date_from: str = None, date_to: str = None) -> Dict:
        """
        查询销售订单列表
        
        API: POST /yonbip/sd/voucherorder/list
        
        Args:
            access_token: API 访问 Token
            page_index: 页码，默认值：1
            page_size: 每页行数，默认值：500
            isSum: True=按订单汇总，False=按商品明细（默认）
            date_from: 起始日期，格式 YYYY-MM-DD，不传则不过滤
            date_to: 截止日期，格式 YYYY-MM-DD，不传则不过滤
            
        Returns:
            API 响应结果
        """
        # access_token 放在 URL 参数中（YonSuite API 要求）
        url = f"{self.gateway_url}{self.base_path}/list?access_token={urllib.parse.quote(access_token)}"
        
        # body 中不包含 access_token，只保留必填参数
        body = {
            "pageIndex": page_index,
            "pageSize": page_size,
            "isSum": isSum,
            "simpleVOs": [],
            "queryOrders": [{"field": "vouchdate", "order": "desc"}]
        }
        
        # 日期范围过滤（API op 必须用 "between"，字段是 "vouchdate"）
        if date_from and date_to:
            body["simpleVOs"] = [{"field": "vouchdate", "op": "between", "value1": date_from, "value2": date_to}]
            logger.info(f"查询销售订单列表，页码：{page_index}，每页：{page_size}，日期范围：{date_from} ~ {date_to}")
        else:
            logger.info(f"查询销售订单列表，页码：{page_index}，每页：{page_size}（无日期过滤）")
        
        result = self._http_post_raw(url, body)
        return self.check_response(result, "查询销售订单列表")
    
    @retry_on_failure()
    def get_order_detail(self, access_token: str, order_id: str) -> Dict:
        """
        查询销售订单详情
        
        Args:
            access_token: API 访问 Token
            order_id: 订单 ID
            
        Returns:
            API 响应结果
        """
        url = f"{self.gateway_url}{self.base_path}/detail"
        params = {'access_token': access_token, 'id': order_id}
        
        logger.info("查询订单详情")
        result = self._http_get(url, params)
        return self.check_response(result, "查询订单详情")
    
    def query_orders_parsed(self, access_token: str) -> List[SaleOrder]:
        """
        查询销售订单列表（解析为模型对象）
        
        Args:
            access_token: API 访问 Token
            
        Returns:
            SaleOrder 对象列表
        """
        result = self.query_orders(access_token)
        data = result.get('data', [])
        if isinstance(data, list):
            return [SaleOrder.from_api(item) for item in data]
        return []
    
    def get_order_detail_parsed(self, access_token: str, order_id: str) -> Optional[SaleOrderDetail]:
        """
        查询销售订单详情（解析为模型对象）
        
        Args:
            access_token: API 访问 Token
            order_id: 订单 ID
            
        Returns:
            SaleOrderDetail 对象，如果未找到则返回 None
        """
        result = self.get_order_detail(access_token, order_id)
        data = result.get('data')
        if data:
            return SaleOrderDetail.from_api(data)
        return None
    
    def format_orders_list(self, orders: List[SaleOrder]) -> str:
        """
        格式化订单列表为可读文本 - 28字段格式
        
        Args:
            orders: 订单列表
            
        Returns:
            格式化的文本
        """
        if not orders:
            return "未找到销售订单"
        
        # 表头
        headers = ['单据编号', '单据日期', '客户', '商品名称', '销售数量', '含税金额', '订单状态']
        col_widths = [18, 12, 15, 20, 12, 15, 10]
        
        lines = [f"📋 找到 {len(orders)} 个销售订单："]
        lines.append("-" * 110)
        
        # 表头行
        header_line = " | ".join(h.ljust(w) for h, w in zip(headers, col_widths))
        lines.append(header_line)
        lines.append("-" * 110)
        
        # 数据行
        for order in orders:
            row = [
                (order.code or '-')[:18],
                (order.vouchdate or '-')[:12],
                (order.customer_name or '-')[:15],
                (order.material_name or '-')[:20],
                f"{order.salenum:,.2f}" if order.salenum else '-',
                f"{order.oriSum:,.2f}" if order.oriSum else '-',
                (order.status or '-')[:10],
            ]
            lines.append(" | ".join(v.ljust(w) for v, w in zip(row, col_widths)))
        
        lines.append("-" * 110)
        
        # 汇总行
        total_amount = sum(o.oriSum for o in orders if o.oriSum)
        total_qty = sum(o.salenum for o in orders if o.salenum)
        lines.append(f"📊 汇总：共 {len(orders)} 单，合计数量 {total_qty:,.2f}，合计金额 ¥{total_amount:,.2f}")
        
        return "\n".join(lines)
