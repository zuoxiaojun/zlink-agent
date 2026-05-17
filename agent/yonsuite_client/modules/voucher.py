#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
凭证管理模块

凭证列表查询 API。
API: POST /yonbip/fi/ficloud/openapi/voucher/queryVouchers
账簿查询 API: POST /yonbip/fi/fipub/basedoc/querybd/accbook
文档:
  - 凭证: https://open.yonyoucloud.com/#/doc-center/docDes/api?apiId=34b5b2e4abbf4cde95d65e1aef999115
  - 账簿: https://open.yonyoucloud.com/#/doc-center/docDes/api?apiId=4dd35a37ce13410e8fc1f6f7e328ff60
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from .base import BaseAPIClient, retry_on_failure
from ..exceptions import YonSuiteAPIError

logger = logging.getLogger(__name__)

# 账簿缓存路径
_CACHE_DIR = Path(__file__).parent.parent / "cache"
_CACHE_ACCBOOK = _CACHE_DIR / "cache_accbook.json"


def round2(v):
    """保留两位小数"""
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return 0.0


class VoucherModule(BaseAPIClient):
    """凭证管理模块"""

    def __init__(self, gateway_url: str = None):
        super().__init__(gateway_url=gateway_url)
        self.base_path = "/yonbip/fi/ficloud/openapi/voucher"
        self.accbook_base = "/yonbip/fi/fipub/basedoc/querybd/accbook"

    def query_accbooks(self, access_token: str) -> List[Dict]:
        """
        查询账簿列表并缓存到本地

        API: POST /yonbip/fi/fipub/basedoc/querybd/accbook

        Args:
            access_token: API 访问 Token

        Returns:
            账簿列表 [{id, code, name}, ...]
        """
        url = f"{self.gateway_url}{self.accbook_base}?access_token={access_token}"
        body = {
            "fields": ["id", "code", "name"],
            "pageSize": 1000
        }
        result = self._http_post_raw(url, body)
        self.check_response(result, "查询账簿列表")

        records = result.get('data', [])
        accbooks = [{"id": r.get("id", ""), "code": r.get("code", ""), "name": r.get("name", "")} for r in records]

        # 缓存到本地
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(_CACHE_ACCBOOK, "w", encoding="utf-8") as f:
            json.dump(accbooks, f, ensure_ascii=False, indent=2)
        logger.info(f"账簿缓存成功：{len(accbooks)} 个")

        return accbooks

    def get_cached_accbooks(self, access_token: str) -> List[Dict]:
        """
        获取账簿（优先本地缓存，缓存不存在则查询并缓存）
        """
        if _CACHE_ACCBOOK.exists():
            with open(_CACHE_ACCBOOK, encoding="utf-8") as f:
                cached = json.load(f)
            if cached:
                return cached
        return self.query_accbooks(access_token)

    @retry_on_failure()
    def query_vouchers(
        self,
        access_token: str,
        page_index: int = 1,
        page_size: int = 20,
        voucher_date_start: Optional[str] = None,
        voucher_date_end: Optional[str] = None,
        department_name_list: Optional[List[str]] = None,
        person_name_list: Optional[List[str]] = None,
        accountant_year: Optional[str] = None,
        accountant_period: Optional[str] = None,
        document_type_name: Optional[str] = None,
        tallyman_name_list: Optional[List[str]] = None,
        billcode_min: Optional[int] = None,
        billcode_max: Optional[int] = None,
        money_range_min: Optional[float] = None,
        money_range_max: Optional[float] = None,
        ts_start: Optional[str] = None,
        ts_end: Optional[str] = None,
        accbook_code: Optional[str] = None,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
    ) -> Dict:
        """
        查询凭证列表

        API: POST /yonbip/fi/ficloud/openapi/voucher/queryVouchers

        Args:
            access_token: API 访问 Token
            page_index: 当前页（默认1）
            page_size: 每页数量（默认20）
            voucher_date_start: 凭证日期区间左端点（格式: yyyy-MM-dd）
            voucher_date_end: 凭证日期区间右端点（格式: yyyy-MM-dd）
            department_name_list: 部门列表
            person_name_list: 制单人列表
            accountant_year: 会计年度
            accountant_period: 会计期间
            document_type_name: 凭证字（如"记"）
            tallyman_name_list: 记账人列表
            billcode_min: 凭证号区间左端点
            billcode_max: 凭证号区间右端点
            money_range_min: 分录金额区间左端点
            money_range_max: 分录金额区间右端点
            ts_start: 最后操作日期区间左端点（格式: yyyy-MM-dd HH:mm:ss）
            ts_end: 最后操作日期区间右端点（格式: yyyy-MM-dd HH:mm:ss）
            accbook_code: 账簿编码（必填，可从 get_cached_accbooks 获取）

        Returns:
            API 响应结果
        """
        import urllib.parse

        url = f"{self.gateway_url}{self.base_path}/queryVouchers?access_token={urllib.parse.quote(access_token)}"

        body: Dict[str, Any] = {
            "pager": {
                "pageIndex": page_index,
                "pageSize": page_size,
            }
        }

        if voucher_date_start:
            body["voucherDateStart"] = voucher_date_start
        if voucher_date_end:
            body["voucherDateEnd"] = voucher_date_end
        if department_name_list:
            body["departmentNameList"] = department_name_list
        if person_name_list:
            body["personNameList"] = person_name_list
        if accountant_year:
            body["accountantYear"] = accountant_year
        if accountant_period:
            body["accountantPeriod"] = accountant_period
        if document_type_name:
            body["documentTypeName"] = document_type_name
        # periodStart / periodEnd 格式 yyyy-MM，如 2026-03
        if period_start:
            body["periodStart"] = period_start
        if period_end:
            body["periodEnd"] = period_end
        if tallyman_name_list:
            body["tallymanNameList"] = tallyman_name_list
        if billcode_min is not None:
            body["billcodeMin"] = billcode_min
        if billcode_max is not None:
            body["billcodeMax"] = billcode_max
        if money_range_min is not None:
            body["moneyRangeMin"] = money_range_min
        if money_range_max is not None:
            body["moneyRangeMax"] = money_range_max
        if ts_start:
            body["tsStart"] = ts_start
        if ts_end:
            body["tsEnd"] = ts_end
        if accbook_code:
            body["accbookCode"] = accbook_code

        logger.info(f"查询凭证列表，页码：{page_index}，每页：{page_size}，账簿：{accbook_code}")
        result = self._http_post_raw(url, body)
        return self.check_response(result, "查询凭证列表")

    def query_vouchers_parsed(self, access_token: str, page_size: int = 500, **kwargs) -> Dict:
        """
        查询凭证列表（解析响应，展平 header + body 结构）

        Returns:
            { pageIndex, pageSize, recordCount, records: [{凭证信息}, ...] }
        """
        result = self.query_vouchers(access_token, page_size=page_size, **kwargs)
        data = result.get('data', {})

        raw_records = data.get('recordList', [])
        records = []
        for r in raw_records:
            header = r.get('header', {})
            body_entries = r.get('body', [])

            # 借方总额、贷方总额
            debit = round2(header.get('totaldebit_org', 0))
            credit = round2(header.get('totalcredit_org', 0))
            maker_info = header.get('maker', {}) or {}
            voucher_type = header.get('vouchertype', {}) or {}

            flat = {
                '凭证ID': header.get('id', ''),
                '凭证号': header.get('billcode', ''),
                '凭证字': voucher_type.get('voucherstr', ''),
                '凭证类型': voucher_type.get('name', ''),
                '凭证状态': header.get('voucherstatus', ''),
                '凭证日期': header.get('maketime', '')[:10] if header.get('maketime') else '',
                '会计期间': header.get('period', ''),
                '制单人': maker_info.get('name', ''),
                '制单人ID': maker_info.get('id', ''),
                '来源系统': header.get('srcsystem', ''),
                '借方总额': debit,
                '贷方总额': credit,
                '分录数': len(body_entries),
            }
            records.append(flat)

        return {
            'pageIndex': data.get('pageIndex', 1),
            'pageSize': data.get('pageSize', 20),
            'recordCount': data.get('recordCount', 0),
            'records': records,
        }

    def format_vouchers_list(self, records: List[Dict], max_rows: int = 30) -> str:
        """
        格式化凭证列表为可读文本
        """
        if not records:
            return "🧾 未找到凭证记录"

        total_debit = sum(r.get('借方总额', 0) for r in records)
        total_credit = sum(r.get('贷方总额', 0) for r in records)

        lines = [f"🧾 凭证列表（共 {len(records)} 条）"]
        lines.append(f"   借方合计：¥{total_debit:,.2f}  |  贷方合计：¥{total_credit:,.2f}")
        lines.append("-" * 70)

        for i, r in enumerate(records[:max_rows], 1):
            debit = r.get('借方总额', 0)
            credit = r.get('贷方总额', 0)
            lines.append(
                f"  {i}. {r.get('凭证日期', '-')}  "
                f"{r.get('凭证字', '')}-{r.get('凭证号', '')}  "
                f"{r.get('制单人', '-')}  "
                f"借¥{debit:,.2f} / 贷¥{credit:,.2f}  "
                f"{r.get('来源系统', '')}"
            )

        if len(records) > max_rows:
            lines.append(f"\n... 还有 {len(records) - max_rows} 条记录")

        return "\n".join(lines)
