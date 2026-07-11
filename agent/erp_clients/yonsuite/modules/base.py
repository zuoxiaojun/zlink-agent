#!/usr/bin/env python3
"""
基础 HTTP 客户端模块

提供统一的 HTTP 请求处理、重试机制、日志记录。
"""

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from functools import wraps
from typing import TypeVar

try:
    import requests

    USE_REQUESTS = True
except ImportError:
    USE_REQUESTS = False

from ..config import config
from ..exceptions import (
    YonSuiteAPIError,
    YonSuiteNetworkError,
    YonSuiteRateLimitError,
    raise_api_error,
)

logger = logging.getLogger(__name__)
T = TypeVar("T")


def retry_on_failure(max_attempts: int | None = None, delay: float | None = None):
    """
    重试装饰器

    Args:
        max_attempts: 最大重试次数
        delay: 初始延迟（秒），每次重试延迟递增
    """
    max_attempts = max_attempts or config.MAX_RETRIES
    delay = delay or config.RETRY_DELAY

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except YonSuiteRateLimitError as e:
                    # 频率限制，使用服务端建议的重试时间
                    retry_after = e.retry_after or (delay * (attempt + 1))
                    logger.warning(f"请求频率限制，等待 {retry_after} 秒后重试...")
                    time.sleep(retry_after)
                    last_error = e
                except YonSuiteAPIError as e:
                    # API 错误，不重试
                    logger.error(f"API 错误：{e}")
                    raise
                except YonSuiteNetworkError as e:
                    # 网络错误，可重试
                    if attempt == max_attempts - 1:
                        raise
                    wait_time = delay * (attempt + 1)
                    logger.warning(f"网络错误：{e}，{wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    last_error = e
                except Exception as e:
                    # 其他错误，不重试
                    logger.error(f"未知错误：{e}")
                    raise

            if last_error:
                raise last_error
            raise YonSuiteNetworkError("重试失败")

        return wrapper

    return decorator


class BaseAPIClient:
    """基础 API 客户端"""

    def __init__(self, gateway_url: str | None = None, token_url: str | None = None):
        """
        初始化客户端

        Args:
            gateway_url: API 网关 URL
            token_url: Token URL
        """
        self.gateway_url = gateway_url or config.GATEWAY_URL
        self.token_url = token_url or config.TOKEN_URL
        self.timeout = config.HTTP_TIMEOUT

    def _http_get(self, url: str, params: dict | None = None, headers: dict | None = None) -> dict:
        """
        HTTP GET 请求

        Args:
            url: 请求 URL
            params: 查询参数
            headers: 请求头

        Returns:
            JSON 响应
        """
        if USE_REQUESTS:
            response = requests.get(url, params=params, headers=headers, timeout=self.timeout)  # type: ignore[possibly-unbound]
            response.raise_for_status()
            return response.json()
        else:
            if params:
                query = urllib.parse.urlencode(params)
                url = f"{url}&{query}" if "?" in url else f"{url}?{query}"

            req = urllib.request.Request(url, headers=headers or {})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8")
                raise YonSuiteNetworkError(f"HTTP {e.code}: {error_body}", e)
            except urllib.error.URLError as e:
                raise YonSuiteNetworkError(f"网络错误：{e.reason}", e)

    def _http_post(self, url: str, json_data: dict, params: dict | None = None, headers: dict | None = None) -> dict:
        """
        HTTP POST 请求（带 params）

        Args:
            url: 请求 URL
            json_data: JSON 数据
            params: 查询参数
            headers: 请求头

        Returns:
            JSON 响应
        """
        if USE_REQUESTS:
            response = requests.post(  # type: ignore[possibly-unbound]
                url,
                params=params,
                json=json_data,
                headers={**(headers or {}), "Content-Type": "application/json"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        else:
            if params:
                query = urllib.parse.urlencode(params)
                url = f"{url}&{query}" if "?" in url else f"{url}?{query}"

            data = json.dumps(json_data, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                method="POST",
                headers={**(headers or {}), "Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8")
                raise YonSuiteNetworkError(f"HTTP {e.code}: {error_body}", e)
            except urllib.error.URLError as e:
                raise YonSuiteNetworkError(f"网络错误：{e.reason}", e)

    def _http_post_raw(self, url: str, json_data: dict, headers: dict | None = None) -> dict:
        """
        HTTP POST 请求（URL 已包含参数）

        Args:
            url: 请求 URL（已包含查询参数）
            json_data: JSON 数据
            headers: 请求头

        Returns:
            JSON 响应
        """
        data = json.dumps(json_data, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                **(headers or {}),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            try:
                error_json = json.loads(error_body)
                # 检查是否是 API 错误
                raise_api_error(error_json, e.code)
            except json.JSONDecodeError:
                raise YonSuiteNetworkError(f"HTTP {e.code}: {error_body}", e)
        except urllib.error.URLError as e:
            raise YonSuiteNetworkError(f"网络错误：{e.reason}", e)

        return {}  # unreachable, but satisfies pyright

    def check_response(self, result: dict, operation: str = "") -> dict:
        """
        检查 API 响应

        Args:
            result: API 响应
            operation: 操作描述（用于错误信息）

        Returns:
            响应结果

        Raises:
            YonSuiteAPIError: 如果响应表示错误
        """
        try:
            raise_api_error(result)
        except YonSuiteAPIError as e:
            if operation:
                logger.error(f"{operation} 失败：{e}")
            raise
        return result

    @staticmethod
    def build_query_params(**kwargs) -> dict:
        """
        构建查询参数（过滤空值）

        Args:
            **kwargs: 参数

        Returns:
            过滤后的参数字典
        """
        return {k: v for k, v in kwargs.items() if v is not None and v != ""}
