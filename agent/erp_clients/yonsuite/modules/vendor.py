#!/usr/bin/env python3
"""
供应商档案管理模块

提供供应商档案查询、详情获取等功能。
"""

import logging

from ..exceptions import YonSuiteAPIError
from ..models import Vendor, VendorDetail
from .base import BaseAPIClient, retry_on_failure

logger = logging.getLogger(__name__)


class VendorModule(BaseAPIClient):
    """供应商档案管理模块"""

    def __init__(self, gateway_url: str | None = None):
        super().__init__(gateway_url=gateway_url)
        self.base_path = "/yonbip/digitalModel/vendor"

    @retry_on_failure()
    def query_vendors(self, access_token: str, page_index: int = 1, page_size: int = 500) -> dict:
        """
        查询供应商档案列表

        API: POST /yonbip/digitalModel/vendor/list

        Args:
            access_token: API 访问 Token
            page_index: 页码，默认值：1
            page_size: 每页行数，默认值：500

        Returns:
            API 响应结果
        """
        import urllib.parse

        url = f"{self.gateway_url}{self.base_path}/list?access_token={urllib.parse.quote(access_token)}"

        body = {"pageIndex": page_index, "pageSize": page_size}

        logger.info(f"查询供应商档案列表，页码：{page_index}，每页：{page_size}")
        result = self._http_post_raw(url, body)
        return self.check_response(result, "查询供应商档案列表")

    @retry_on_failure()
    def get_vendor_detail(self, access_token: str, vendor_id: str, org_id: str | None = None) -> dict:
        """
        查询供应商档案详情

        API: GET /yonbip/digitalModel/vendor/detail

        Args:
            access_token: API 访问 Token
            vendor_id: 供应商档案 ID（必填）
            org_id: 组织 ID（可选，不传则查询管理组织）

        Returns:
            API 响应结果
        """
        url = f"{self.gateway_url}{self.base_path}/detail"
        params = {"access_token": access_token, "id": vendor_id}
        if org_id:
            params["orgId"] = org_id

        logger.info(f"查询供应商详情：id={vendor_id}")
        result = self._http_get(url, params)
        return self.check_response(result, "查询供应商档案详情")

    def query_vendors_parsed(self, access_token: str, unique: bool = True) -> list[Vendor]:
        """
        查询供应商档案列表（解析为模型对象）

        Args:
            access_token: API 访问 Token
            unique: 是否去重（默认 True），只保留管理组织创建的供应商（isCreator=true）

        Returns:
            Vendor 对象列表
        """
        result = self.query_vendors(access_token)
        data = result.get("data", {})
        if isinstance(data, dict):
            data = data.get("recordList", [])

        if isinstance(data, list):
            if unique:
                seen_ids = set()
                unique_data = []
                for item in data:
                    vendor_id = item.get("id")
                    is_creator = item.get("isCreator", False)
                    if vendor_id and is_creator and vendor_id not in seen_ids:
                        unique_data.append(item)
                        seen_ids.add(vendor_id)
                logger.info(
                    f"供应商去重：API 返回 {len(data)} 条，去重后 {len(unique_data)} 个唯一供应商（仅管理组织）"
                )
                return [Vendor.from_api(item) for item in unique_data]
            return [Vendor.from_api(item) for item in data]
        return []

    def get_vendor_detail_parsed(
        self, access_token: str, vendor_id: str, org_id: str | None = None
    ) -> VendorDetail | None:
        """
        查询供应商档案详情（解析为模型对象）

        Args:
            access_token: API 访问 Token
            vendor_id: 供应商档案 ID
            org_id: 组织 ID（可选）

        Returns:
            VendorDetail 对象，如果未找到则返回 None
        """
        result = self.get_vendor_detail(access_token, vendor_id, org_id)
        data = result.get("data")
        if data:
            return VendorDetail.from_api(data)
        return None

    def format_vendors_list(self, vendors: list[Vendor]) -> str:
        """
        格式化供应商列表为可读文本

        Args:
            vendors: 供应商列表

        Returns:
            格式化的文本
        """
        if not vendors:
            return "🏢 未找到供应商记录"

        lines = [f"🏢 找到 {len(vendors)} 个供应商："]
        lines.append("-" * 70)

        for i, vendor in enumerate(vendors, 1):
            lines.append(f"\n【供应商 {i}】")
            lines.append(f"   供应商编码：{vendor.code}")
            lines.append(f"   供应商名称：{vendor.name}")
            lines.append(f"   分类：{vendor.vendor_class}")
            if vendor.contact_person:
                lines.append(f"   联系人：{vendor.contact_person}")
            if vendor.phone:
                lines.append(f"   电话：{vendor.phone}")
            if vendor.bank_name:
                lines.append(f"   开户行：{vendor.bank_name}")
            if vendor.bank_account:
                lines.append(f"   银行账号：{vendor.bank_account}")

        return "\n".join(lines)

    def format_vendor_detail(self, vendor: VendorDetail) -> str:
        """
        格式化供应商详情为可读文本

        Args:
            vendor: 供应商详情对象

        Returns:
            格式化的文本
        """
        lines = [
            "🏢 供应商档案详情",
            f"   供应商编码：{vendor.code}",
            f"   供应商名称：{vendor.name}",
            f"   分类：{vendor.vendor_class}",
            f"   状态：{vendor.status}",
        ]

        if vendor.contact_person or vendor.phone or vendor.email:
            lines.append("\n📞 联系信息：")
            if vendor.contact_person:
                lines.append(f"   联系人：{vendor.contact_person}")
            if vendor.phone:
                lines.append(f"   电话：{vendor.phone}")
            if vendor.email:
                lines.append(f"   邮箱：{vendor.email}")

        if vendor.address:
            lines.append(f"\n📍 地址：{vendor.address}")

        if vendor.bank_name or vendor.bank_account:
            lines.append("\n🏦 银行信息：")
            if vendor.bank_name:
                lines.append(f"   开户行：{vendor.bank_name}")
            if vendor.bank_account:
                lines.append(f"   银行账号：{vendor.bank_account}")

        # 显示更多信息
        if vendor.contacts:
            lines.append(f"\n📋 联系信息列表：{len(vendor.contacts)} 条")
        if vendor.addresses:
            lines.append(f"📍 地址列表：{len(vendor.addresses)} 条")
        if vendor.bank_accounts:
            lines.append(f"🏦 银行账户列表：{len(vendor.bank_accounts)} 条")
        if vendor.qualifications:
            lines.append(f"📜 资质信息：{len(vendor.qualifications)} 条")

        return "\n".join(lines)

    @retry_on_failure()
    def query_vendors_batch(self, access_token: str, vendor_ids: list[str], org_id: str | None = None) -> dict:
        """
        批量查询供应商档案详情

        ⭐ 新增功能：一次查询多个供应商的完整档案信息

        API: POST /yonbip/digitalModel/vendor/batchGet

        Args:
            access_token: API 访问 Token
            vendor_ids: 供应商 ID 列表（最多 100 个）
            org_id: 组织 ID（可选，不传则查询管理组织）

        Returns:
            API 响应结果，包含多个供应商的完整档案信息
        """
        import urllib.parse

        if not vendor_ids:
            raise YonSuiteAPIError("供应商 ID 列表不能为空", error_code="INVALID_PARAMS")

        if len(vendor_ids) > 100:
            logger.warning(f"供应商 ID 数量超过 100，将分批查询：{len(vendor_ids)}个")

        url = f"{self.gateway_url}{self.base_path}/batchGet?access_token={urllib.parse.quote(access_token)}"

        body = {
            "ids": vendor_ids[:100],  # 限制单次最多 100 个
        }
        if org_id:
            body["orgId"] = org_id  # type: ignore[assignment]

        logger.info(f"批量查询供应商详情：共{len(vendor_ids)}个供应商")
        result = self._http_post_raw(url, body)
        return self.check_response(result, "批量查询供应商档案详情")

    def query_vendors_batch_parsed(
        self, access_token: str, vendor_ids: list[str], org_id: str | None = None
    ) -> list[VendorDetail]:
        """
        批量查询供应商档案详情（解析为模型对象）

        Args:
            access_token: API 访问 Token
            vendor_ids: 供应商 ID 列表
            org_id: 组织 ID（可选）

        Returns:
            VendorDetail 对象列表
        """
        result = self.query_vendors_batch(access_token, vendor_ids, org_id)
        data = result.get("data", [])
        if isinstance(data, list):
            return [VendorDetail.from_api(item) for item in data]
        return []

    def format_vendors_batch(self, vendors: list[VendorDetail]) -> str:
        """
        格式化批量供应商查询结果为可读文本

        Args:
            vendors: 供应商详情列表

        Returns:
            格式化的文本
        """
        if not vendors:
            return "🏢 未找到供应商记录"

        lines = [f"🏢 批量查询结果：共 {len(vendors)} 个供应商"]
        lines.append("=" * 70)

        for i, vendor in enumerate(vendors, 1):
            lines.append(f"\n【供应商 {i}/{len(vendors)}】")
            lines.append(f"   编码：{vendor.code}")
            lines.append(f"   名称：{vendor.name}")
            lines.append(f"   分类：{vendor.vendor_class}")
            if vendor.contact_person:
                lines.append(f"   联系人：{vendor.contact_person}")
            if vendor.phone:
                lines.append(f"   电话：{vendor.phone}")
            if vendor.bank_name:
                lines.append(f"   开户行：{vendor.bank_name}")
            lines.append("-" * 50)

        return "\n".join(lines)

    @retry_on_failure()
    def query_vendors_listv3(
        self,
        access_token: str,
        ids: str | None = None,
        code: str | None = None,
        name: str | None = None,
        vendorcontactss_need_query: bool = True,
        vendorbanks_need_query: bool = True,
        vendor_addresses_need_query: bool = True,
        vendor_qualifies_need_query: bool = True,
        vendor_orgs_need_query: bool = True,
        vendor_extend_need_query_all: bool = True,
        page_index: int = 1,
        page_size: int = 10,
    ) -> dict:
        """
        供应商档案批量详情查询（listV3 接口）⭐ 新增

        📌 官方文档：https://open.yonyoucloud.com/#/doc-center/docDes/api?apiId=2151560680253685764

        ⚠️ 权限要求：此接口需要单独授权，如遇 403 错误需联系用友管理员开通
           `/yonbip/digitalModel/vendor/listV3` 接口权限

        Args:
            access_token: API 访问 Token
            ids: 供应商 ID 列表，多个 ID 逗号分隔（如 "id1,id2,id3"）
            code: 供应商编码（模糊查询）
            name: 供应商名称（模糊查询）
            vendorcontactss_need_query: 是否查询联系人子表（默认 True）
            vendorbanks_need_query: 是否查询银行子表（默认 True）
            vendor_addresses_need_query: 是否查询地址子表（默认 True）
            vendor_qualifies_need_query: 是否查询资质子表（默认 True）
            vendor_orgs_need_query: 是否查询适用范围子表（默认 True）
            vendor_extend_need_query_all: 是否查询所有业务信息（默认 True）
            page_index: 页号（默认 1）
            page_size: 每页行数（默认 10）

        Returns:
            API 响应结果，包含：
            - code: 返回码（200 表示成功）
            - message: 消息
            - data: 包含 recordList（供应商详情列表）、pageCount、recordCount 等

        Example:
            # 批量查询 3 个供应商的完整档案
            result = client.vendor.query_vendors_listv3(
                token,
                ids="id1,id2,id3",
                vendorcontactss_need_query=True,
                vendorbanks_need_query=True
            )
            vendors = result.get('data', {}).get('recordList', [])
        """
        import urllib.parse

        url = f"{self.gateway_url}{self.base_path}/listV3?access_token={urllib.parse.quote(access_token)}"

        body = {
            "pageIndex": page_index,
            "pageSize": page_size,
        }

        if ids:
            body["ids"] = ids  # type: ignore[assignment]
        if code:
            body["code"] = code  # type: ignore[assignment]
        if name:
            body["name"] = name  # type: ignore[assignment]

        # 子表查询选项
        body["vendorcontactssNeedQuery"] = vendorcontactss_need_query
        body["vendorbanksNeedQuery"] = vendorbanks_need_query
        body["vendorAddressesNeedQuery"] = vendor_addresses_need_query
        body["vendorQualifiesNeedQuery"] = vendor_qualifies_need_query
        body["vendorOrgsNeedQuery"] = vendor_orgs_need_query
        body["vendorextendNeedQueryAll"] = (
            vendor_extend_need_query_all if vendor_extend_need_query_all is not None else True
        )

        logger.info(f"listV3 批量查询供应商：ids={ids}, name={name}")
        result = self._http_post_raw(url, body)
        return self.check_response(result, "供应商档案批量详情查询 (listV3)")
