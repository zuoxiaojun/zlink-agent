"""
ERP 客户端统一入口 (v1.5.0 声明性注册中心)

- 不再硬编码 ERP 客户端类
- 只导出通用异常 + Protocol + MCPStarterConfig
- 实际启动由 mcp_manager.py 负责
"""

# 触发 YonSuite 子包的导入 (YonSuiteClient 仍暴露为 Python 类入口)
from . import yonsuite  # noqa: F401
from .base import (
    ERPAPIError,
    ERPAuthError,
    ERPClient,
    ERPError,
    ERPNetworkError,
    ERPRateLimitError,
    MCPStarterConfig,
)

__all__ = [
    "ERPClient",
    "ERPError",
    "ERPAuthError",
    "ERPRateLimitError",
    "ERPNetworkError",
    "ERPAPIError",
    "MCPStarterConfig",
]
