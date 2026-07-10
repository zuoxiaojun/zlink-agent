"""
ERP 客户端抽象层（声明性 Protocol）

v1.5.0 角色:
- 定义所有 ERP 客户端应满足的最小接口 (Protocol)
- 定义跨 ERP 的通用异常类型
- 不强制任何 MCP server 继承, 也不强制 YonSuiteClient 实现
- 主要用于: 类型注解、isinstance 检查、文档生成
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

# === 通用异常 ===


class ERPError(Exception):
    """所有 ERP 客户端错误的基类"""


class ERPAuthError(ERPError):
    """认证失败 (token 过期/无效)"""


class ERPRateLimitError(ERPError):
    """频率限制"""

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class ERPNetworkError(ERPError):
    """网络错误"""


class ERPAPIError(ERPError):
    """API 业务错误"""

    def __init__(self, code: int | str, message: str, response: dict | None = None):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.response = response or {}


# === 抽象协议 (声明性, 非强制) ===


@runtime_checkable
class ERPClient(Protocol):
    """
    所有 ERP 客户端的最小接口契约 (v1.5.0 声明性版本)

    注意: v1.5.0 实际不强制实现, 因为 NC 走 MCP 不走 Python 类
    保留此 Protocol 仅为:
    - YonSuiteClient 的 isinstance 检查 (结构子类型)
    - 未来可能新增的"嵌入式 ERP 客户端"扩展点
    """

    name: str

    def authenticate(self, force_refresh: bool = False) -> str | bool: ...
    def health_check(self) -> bool: ...


# === MCP 启动配置 schema ===


@dataclass(frozen=True)
class MCPStarterConfig:
    """
    把用户友好配置转换为 MCP server 启动参数

    用于 agent/mcp_server/nc_mcp/mcp_starter.py 等
    """

    erp_name: str
    enabled: bool
    command: str
    args: list[str]
    env: dict[str, str]
    builtin: bool
    install_hint: str | None = None
