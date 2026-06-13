#!/usr/bin/env python3
"""
客户档案管理模块

提供客户档案查询等功能。
"""

import logging
from typing import Any

from ..exceptions import YonSuiteAPIError
from ..models import Customer
from .base import BaseAPIClient, retry_on_failure

logger = logging.getLogger(__name__)


class CustomerModule(BaseAPIClient):
    """客户档案管理模块"""

    def __init__(self, gateway_url: str = None):
        super().__init__(gateway_url=gateway_url)
        self.base_path = "/yonbip/digitalModel/merchant"

    @retry_on_failure()
    def query_customers(self, access_token: str, page_index: int = 1, page_size: int = 500) -> dict:
        """
        查询客户档案列表

        API: POST /yonbip/digitalModel/merchant/newlistrange

        Args:
            access_token: API 访问 Token
            page_index: 页码，默认值：1
            page_size: 每页行数，默认值：500

        Returns:
            API 响应结果
        """
        import urllib.parse

        # access_token 放在 URL 参数中（YonSuite API 要求）
        url = f"{self.gateway_url}{self.base_path}/newlistrange?access_token={urllib.parse.quote(access_token)}"

        # body 中不包含 access_token，只保留必填参数
        body = {"pageIndex": page_index, "pageSize": page_size}

        logger.info(f"查询客户档案列表，页码：{page_index}，每页：{page_size}")
        result = self._http_post_raw(url, body)
        return self.check_response(result, "查询客户档案列表")

    def query_customers_parsed(self, access_token: str) -> list[Customer]:
        """
        查询客户档案列表（解析为模型对象）

        Args:
            access_token: API 访问 Token

        Returns:
            Customer 对象列表
        """
        result = self.query_customers(access_token)
        data = result.get("data", [])
        if isinstance(data, list):
            return [Customer.from_api(item) for item in data]
        return []

    def format_customers_list(self, customers: list[Customer]) -> str:
        """
        格式化客户列表为可读文本

        Args:
            customers: 客户列表

        Returns:
            格式化的文本
        """
        if not customers:
            return "👥 未找到客户记录"

        lines = [f"👥 找到 {len(customers)} 个客户："]
        lines.append("-" * 70)

        for i, customer in enumerate(customers, 1):
            lines.append(f"\n【客户 {i}】")
            lines.append(f"   客户编码：{customer.code}")
            lines.append(f"   客户名称：{customer.name}")
            lines.append(f"   客户分类：{customer.customer_class}")
            if customer.contact_person:
                lines.append(f"   联系人：{customer.contact_person}")
            if customer.phone:
                lines.append(f"   电话：{customer.phone}")
            if customer.email:
                lines.append(f"   邮箱：{customer.email}")

        return "\n".join(lines)

    @retry_on_failure()
    def query_customer_details_batch(
        self,
        access_token: str,
        customer_list: list[dict[str, Any]],
        belong_org_id: str | None = None,
        belong_org_code: str | None = None,
    ) -> dict:
        """
        批量查询客户档案详情

        API: POST /yonbip/digitalModel/merchant/newBatchDetail

        Args:
            access_token: API 访问 Token
            customer_list: 客户查询条件列表，每项包含：
                - id: 客户 ID（可选，与 code 至少传一个）
                - code: 客户编码（可选，与 id 至少传一个）
                - belongOrgId: 使用组织 ID（可选）
                - belongOrgCode: 使用组织编码（可选）
            belong_org_id: 默认使用组织 ID（可选）
            belong_org_code: 默认使用组织编码（可选）

        Returns:
            API 响应结果，包含完整的客户档案信息
        """
        import urllib.parse

        url = f"{self.gateway_url}{self.base_path}/newBatchDetail?access_token={urllib.parse.quote(access_token)}"

        # 构建批量查询参数
        batch_params = []
        for cust in customer_list:
            param = {}
            if "id" in cust:
                param["id"] = cust["id"]
            if "code" in cust:
                param["code"] = cust["code"]
            if "belongOrgId" in cust:
                param["belongOrgId"] = cust["belongOrgId"]
            elif belong_org_id:
                param["belongOrgId"] = belong_org_id
            if "belongOrgCode" in cust:
                param["belongOrgCode"] = cust["belongOrgCode"]
            elif belong_org_code:
                param["belongOrgCode"] = belong_org_code

            if param:
                batch_params.append(param)

        if not batch_params:
            raise YonSuiteAPIError("批量查询参数不能为空", error_code="INVALID_PARAMS")

        logger.info(f"批量查询客户详情：共{len(batch_params)}个客户")
        result = self._http_post_raw(url, batch_params)
        return self.check_response(result, "批量查询客户详情")

    def query_customer_detail_single(
        self,
        access_token: str,
        customer_id: str | None = None,
        customer_code: str | None = None,
        belong_org_id: str | None = None,
        belong_org_code: str | None = None,
    ) -> dict:
        """
        查询单个客户档案详情（批量接口的简化版）

        Args:
            access_token: API 访问 Token
            customer_id: 客户 ID（与 customer_code 至少传一个）
            customer_code: 客户编码（与 customer_id 至少传一个）
            belong_org_id: 使用组织 ID（可选）
            belong_org_code: 使用组织编码（可选）

        Returns:
            API 响应结果（data 字段为单个客户详情）
        """
        customer_list = [{"id": customer_id} if customer_id else {"code": customer_code}]
        result = self.query_customer_details_batch(access_token, customer_list, belong_org_id, belong_org_code)

        data = result.get("data", [])
        if isinstance(data, list) and len(data) > 0:
            result["data"] = data[0]
        return result

    def format_customer_detail(self, detail: dict) -> str:
        """
        格式化单个客户详情为可读文本

        Args:
            detail: 客户详情字典

        Returns:
            格式化的文本字符串
        """
        if not detail:
            return "未找到客户信息"

        lines = []

        # 基本信息
        lines.append("📋 客户基本信息")
        lines.append(f"  客户 ID: {detail.get('id', 'N/A')}")
        lines.append(f"  客户编码：{detail.get('code', 'N/A')}")

        name_obj = detail.get("name", {})
        if name_obj:
            lines.append(f"  客户名称：{name_obj.get('simplifiedName', 'N/A')}")

        lines.append(f"  客户类型：{detail.get('transTypeCode', 'N/A')}")
        lines.append(f"  管理组织：{detail.get('createOrgCode', 'N/A')}")

        # 资质信息
        lines.append("\n📄 资质信息")
        license_types = {
            0: "统一社会信用代码",
            1: "营业执照",
            2: "其他证照",
            3: "居民身份证",
            4: "护照",
            5: "其他身份证件",
        }
        lines.append(f"  证照类型：{license_types.get(detail.get('licenseType'), 'N/A')}")
        lines.append(f"  证照号码：{detail.get('creditCode', 'N/A')}")
        lines.append(f"  法人代表：{detail.get('leaderName', 'N/A')}")
        lines.append(f"  成立时间：{detail.get('buildTime', 'N/A')}")
        lines.append(f"  注册资金：{detail.get('money', 'N/A')} {detail.get('currencyCode', 'N/A')}")

        # 联系信息
        lines.append("\n📞 联系信息")
        lines.append(f"  联系人：{detail.get('contactName', 'N/A')}")
        lines.append(f"  联系电话：{detail.get('contactTel', 'N/A')}")
        lines.append(f"  邮箱：{detail.get('email', 'N/A')}")
        lines.append(f"  网址：{detail.get('website', 'N/A')}")

        # 地址信息
        address_infos = detail.get("merchantAddressInfos", [])
        if address_infos:
            lines.append(f"\n📍 地址信息（共{len(address_infos)}条）")
            for i, addr in enumerate(address_infos[:3], 1):
                lines.append(
                    f"  {i}. {addr.get('address', 'N/A')} - {addr.get('receiver', 'N/A')} {addr.get('mobile', 'N/A')}"
                )

        # 联系人信息
        contact_infos = detail.get("merchantContactInfos", [])
        if contact_infos:
            lines.append(f"\n👥 联系人信息（共{len(contact_infos)}条）")
            for i, contact in enumerate(contact_infos[:3], 1):
                full_name = contact.get("fullName", {})
                lines.append(f"  {i}. {full_name.get('simplifiedName', 'N/A')} - {contact.get('mobile', 'N/A')}")

        # 银行信息
        financial_infos = detail.get("merchantAgentFinancialInfos", [])
        if financial_infos:
            lines.append(f"\n🏦 银行信息（共{len(financial_infos)}条）")
            for i, fin in enumerate(financial_infos[:3], 1):
                lines.append(f"  {i}. {fin.get('bankName', 'N/A')} - {fin.get('bankAccount', 'N/A')}")

        # 发票信息
        invoice_infos = detail.get("merchantAgentInvoiceInfos", [])
        if invoice_infos:
            lines.append(f"\n🧾 发票信息（共{len(invoice_infos)}条）")
            for i, inv in enumerate(invoice_infos[:3], 1):
                lines.append(f"  {i}. {inv.get('title', 'N/A')} - 税号：{inv.get('taxNo', 'N/A')}")

        return "\n".join(lines)
