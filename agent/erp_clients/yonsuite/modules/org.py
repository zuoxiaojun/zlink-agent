#!/usr/bin/env python3
"""
组织档案查询模块

提供业务单元（组织）详情查询功能。
API: GET /yonbip/digitalModel/orgunit/detail
"""

import logging

from .base import BaseAPIClient, retry_on_failure

logger = logging.getLogger(__name__)


class OrgModule(BaseAPIClient):
    """组织档案查询模块"""

    def __init__(self, gateway_url: str | None = None):
        super().__init__(gateway_url=gateway_url)
        self.base_path = "/yonbip/digitalModel/orgunit"

    @retry_on_failure()
    def get_org_detail(self, access_token: str, org_id: str) -> dict:
        """
        查询业务单元（组织）详情

        API: GET /yonbip/digitalModel/orgunit/detail

        Args:
            access_token: API 访问 Token
            org_id: 组织 ID（必填）

        Returns:
            API 响应结果，包含组织完整信息
        """
        import urllib.parse

        url = f"{self.gateway_url}{self.base_path}/detail?access_token={urllib.parse.quote(access_token)}&id={org_id}"
        logger.info(f"查询组织详情：id={org_id}")
        result = self._http_get(url)  # no extra params, token+id already in URL
        return self.check_response(result, "查询组织详情")

    @retry_on_failure()
    def query_org_units(self, access_token: str, **kwargs) -> dict:
        """
        批量查询业务单元/部门（V2）

        API: POST /yonbip/digitalModel/OrgUnitSync/orgUnitDataSyncByDTO

        Args:
            access_token: API 访问 Token
            **kwargs: 查询参数，支持：
                - funcTypeCode (str): 职能类型，默认 orgunit
                  可选: orgunit(组织单元), adminorg(人力资源组织), factoryorg(工厂组织),
                       inventoryorg(库存组织), salesorg(销售组织), assetsorg(资产组织),
                       energyorg(能源组织), researchdeveloporg(研发组织), purchaseorg(采购组织),
                       financeorg(会计主体), safetyorg(安环组织), serviceorg(服务组织),
                       qualityorg(质检组织), taxpayerorg(纳税主体), planorg(计划组织)
                - ids (list): 组织 ID 列表
                - codes (list): 组织编码列表
                - objids (list): 外部系统主键列表
                - name (str): 组织名称（模糊匹配）
                - dr (str): 删除标识，0-未删除，1-已删除
                - enable (str): 启用状态，0-未启用，1-启用，2-停用
                - pubts (str): 时间戳，查询大于等于该时间的数据，格式：YYYY-MM-DD HH:MM:SS
                - parentId (str): 上级组织 ID
                - parentCode (str): 上级组织编码
                - orgDept (str): 查询范围，org-业务单元，dept-部门，不填查全部
                - sourceType (str): 数据来源，1-系统默认，默认1
                - externalOrg (str): 外部组织，0-不是，1-是，默认0
                - pageSize (int): 每页行数，默认10
                - pageIndex (int): 当前页数，默认1

        Returns:
            分页结果，包含 recordList（组织列表）、pageIndex、pageSize、recordCount 等
        """
        import urllib.parse

        url = f"{self.gateway_url}{self.base_path.replace('orgunit', 'OrgUnitSync')}/orgUnitDataSyncByDTO?access_token={urllib.parse.quote(access_token)}"

        # 构建请求体
        body = {}
        if kwargs.get("ids"):
            body["ids"] = kwargs["ids"]
        if kwargs.get("codes"):
            body["codes"] = kwargs["codes"]
        if kwargs.get("objids"):
            body["objids"] = kwargs["objids"]
        if kwargs.get("name"):
            body["name"] = kwargs["name"]
        if kwargs.get("dr"):
            body["dr"] = kwargs["dr"]
        if kwargs.get("enable"):
            body["enable"] = kwargs["enable"]
        if kwargs.get("pubts"):
            body["pubts"] = kwargs["pubts"]
        if kwargs.get("parentId"):
            body["parentId"] = kwargs["parentId"]
        if kwargs.get("parentCode"):
            body["parentCode"] = kwargs["parentCode"]
        if kwargs.get("orgDept"):
            body["orgDept"] = kwargs["orgDept"]
        if kwargs.get("sourceType"):
            body["sourceType"] = kwargs["sourceType"]
        if kwargs.get("externalOrg"):
            body["externalOrg"] = kwargs["externalOrg"]
        if kwargs.get("pageSize"):
            body["pageSize"] = str(kwargs["pageSize"])
        if kwargs.get("pageIndex"):
            body["pageIndex"] = str(kwargs["pageIndex"])

        # 默认 funcTypeCode 为 orgunit
        body.setdefault("funcTypeCode", kwargs.get("funcTypeCode", "orgunit"))

        logger.info(f"批量查询组织：funcTypeCode={body.get('funcTypeCode')}, orgDept={kwargs.get('orgDept', '全部')}")
        result = self._http_post_raw(url, body)
        return self.check_response(result, "批量查询组织")

    def format_org_info(self, data: dict) -> str:
        """
        格式化组织信息为可读文本

        Args:
            data: 组织详情数据

        Returns:
            格式化的文本
        """
        name_obj = data.get("name", {})
        if isinstance(name_obj, dict):
            name = name_obj.get("zh_CN", "—")
        else:
            name = str(name_obj)

        shortname_obj = data.get("shortname", {})
        if isinstance(shortname_obj, dict):
            shortname = shortname_obj.get("zh_CN", "—")
        else:
            shortname = str(shortname_obj) if shortname_obj else "—"

        enable_map = {0: "未启用", 1: "启用", 2: "停用"}
        enable = enable_map.get(data.get("enable", -1), "未知")

        lines = [
            f"🏢 {name} ({data.get('code', '?')})",
            f"   组织ID: {data.get('id', '?')}",
            f"   简称：{shortname}",
            f"   组织形态：{data.get('companytype_name', '—')}",
            f"   状态：{enable}",
            f"   纳税人名称：{data.get('taxpayername', '—')}",
            f"   纳税人识别号：{data.get('taxpayerid', '—')}",
            f"   创建时间：{data.get('creationtime', '—')}",
            f"   修改时间：{data.get('modifiedtime', '—')}",
        ]

        # 组织类型信息
        org_type = "部门" if data.get("orgtype") == 2 else ("组织" if data.get("orgtype") == 1 else "未知")
        lines.append(f"   组织类型：{org_type}")

        return "\n".join(lines)
