#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户待办查询模块

提供用户待办数据查询功能，支持查询待办/已办列表。

API: GET /yonbip/uspace/rest/open/yhttoken/todo/query/list
"""

import logging
import urllib.parse
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from .base import BaseAPIClient, retry_on_failure
from ..exceptions import YonSuiteAPIError

logger = logging.getLogger(__name__)


@dataclass
class TodoItem:
    """待办事项数据模型"""
    
    tenant_id: str = ""
    user_id: str = ""
    primary_id: str = ""
    app_id: str = ""
    business_key: str = ""
    title: str = ""
    content: str = ""
    rich_text: str = ""
    m_url: str = ""
    web_url: str = ""
    done_status: int = 0  # 0=待办，1=已办
    approve_source: str = ""
    form_id: str = ""
    service_code: str = ""
    group_id: str = ""
    org_id: str = ""
    commit_user_id: str = ""
    commit_ts_long: int = 0
    create_ts_long: int = 0
    update_ts_long: int = 0
    finish_ts_long: int = 0
    msg_ts_long: int = 0
    
    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> 'TodoItem':
        """从 API 响应创建待办事项对象"""
        return cls(
            tenant_id=data.get('tenantId', ''),
            user_id=data.get('userId', ''),
            primary_id=data.get('primaryId', ''),
            app_id=data.get('appId', ''),
            business_key=data.get('businessKey', ''),
            title=data.get('title', ''),
            content=data.get('content', ''),
            rich_text=data.get('richText', ''),
            m_url=data.get('mUrl', ''),
            web_url=data.get('webUrl', ''),
            done_status=data.get('doneStatus', 0),
            approve_source=data.get('approveSource', ''),
            form_id=data.get('formId', ''),
            service_code=data.get('serviceCode', ''),
            group_id=data.get('groupId', ''),
            org_id=data.get('orgid', ''),
            commit_user_id=data.get('commitUserId', ''),
            commit_ts_long=data.get('commitTsLong', 0),
            create_ts_long=data.get('createTsLong', 0),
            update_ts_long=data.get('updateTsLong', 0),
            finish_ts_long=data.get('finishTsLong', 0),
            msg_ts_long=data.get('msgTsLong', 0),
        )
    
    def format(self) -> str:
        """格式化为可读文本"""
        status = "✅ 已办" if self.done_status == 1 else "⏳ 待办"
        lines = [
            f"标题：{self.title}",
            f"状态：{status}",
            f"内容：{self.content}",
            f"来源：{self.approve_source}",
            f"表单：{self.form_id}",
        ]
        if self.web_url:
            lines.append(f"链接：{self.web_url[:100]}...")
        return "\n  ".join(lines)
    
    @property
    def is_todo(self) -> bool:
        """是否为待办（未完成）"""
        return self.done_status == 0
    
    @property
    def is_done(self) -> bool:
        """是否为已办（已完成）"""
        return self.done_status == 1


class TodoModule(BaseAPIClient):
    """用户待办查询模块"""
    
    def __init__(self, gateway_url: str = None):
        super().__init__(gateway_url=gateway_url)
        self.base_path = "/yonbip/uspace/rest/open/yhttoken/todo/query/list"
    
    @retry_on_failure()
    def query_todos(self, 
                    access_token: str, 
                    page_no: int = 1, 
                    page_size: int = 10) -> Dict:
        """
        查询用户待办数据列表
        
        API: GET /yonbip/uspace/rest/open/yhttoken/todo/query/list
        
        Args:
            access_token: API 访问 Token
            page_no: 页码，默认值：1
            page_size: 每页行数，默认值：10
            
        Returns:
            API 响应结果，包含：
            - flag: 标志位
            - msg: 消息
            - result: 待办数据列表
            - displayCode: 错误码（如有）
            
        Raises:
            YonSuiteAPIError: API 调用失败时抛出
        """
        # 构建 URL 参数，只保留必填参数
        params = {
            'access_token': access_token,
            'status': 'todo',
            'pageNo': page_no,
            'pageSize': page_size
        }
        
        query_string = urllib.parse.urlencode(params)
        url = f"{self.gateway_url}{self.base_path}?{query_string}"
        
        logger.info(f"查询待办事项列表，页码：{page_no}，每页：{page_size}")
        result = self._http_get(url)
        
        # 检查响应
        if result.get('code') == '200':
            data = result.get('data', {})
            if data.get('flag') == 0:
                logger.info(f"待办查询成功，共 {len(data.get('result', []))} 条")
                return {
                    'code': '200',
                    'message': result.get('message', ''),
                    'data': data.get('result', []),
                    'displayCode': data.get('displayCode', '')
                }
            else:
                raise YonSuiteAPIError(
                    error_code=data.get('displayCode', 'UNKNOWN'),
                    message=f"待办查询失败：{data.get('msg', '未知错误')}"
                )
        else:
            raise YonSuiteAPIError(
                error_code=result.get('code', 'UNKNOWN'),
                message=f"待办查询失败：{result.get('message', '未知错误')}"
            )
    
    def query_todos_parsed(self, 
                           access_token: str, 
                           page_no: int = 1, 
                           page_size: int = 10) -> List[TodoItem]:
        """
        查询用户待办数据（解析为模型对象）
        
        Args:
            access_token: API 访问 Token
            page_no: 页码，默认值：1
            page_size: 每页行数，默认值：10
            
        Returns:
            TodoItem 对象列表
        """
        result = self.query_todos(access_token, page_no, page_size)
        data = result.get('data', [])
        if isinstance(data, list):
            return [TodoItem.from_api(item) for item in data]
        return []
    
    def query_todo_count(self, 
                         access_token: str,
                         status: str = "todo") -> int:
        """
        查询待办/已办数量
        
        Args:
            access_token: API 访问 Token
            status: 待办状态，todo=待办，done=已办
            
        Returns:
            待办/已办数量
        """
        # 只查询第一页，获取总数（需要 API 支持总数返回）
        # 目前 API 只返回列表，需要分页获取全部
        result = self.query_todos(access_token, status, page_no=1, page_size=1)
        # 这里返回的是第一页的数据，实际总数需要遍历所有页
        # 暂时返回当前页数量
        return len(result.get('data', []))
    
    def format_todos(self, todo_items: List[TodoItem]) -> str:
        """
        格式化待办列表为可读文本
        
        Args:
            todo_items: 待办事项列表
            
        Returns:
            格式化的文本
        """
        if not todo_items:
            return "📋 暂无待办事项"
        
        todo_count = sum(1 for item in todo_items if item.is_todo)
        done_count = sum(1 for item in todo_items if item.is_done)
        
        lines = [f"📋 待办事项：共 {len(todo_items)} 条（待办：{todo_count}, 已办：{done_count}）"]
        lines.append("-" * 70)
        
        for i, item in enumerate(todo_items, 1):
            lines.append(f"\n【待办 {i}】")
            lines.append(item.format())
        
        return "\n".join(lines)
