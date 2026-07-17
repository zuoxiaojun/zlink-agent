"""
ERP 客户端统一入口 (v1.5.0)

- 触发 YonSuite 子包导入
- 导出通用异常 + Protocol
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
)

__all__ = [
    "ERPClient",
    "ERPError",
    "ERPAuthError",
    "ERPRateLimitError",
    "ERPNetworkError",
    "ERPAPIError",
]
