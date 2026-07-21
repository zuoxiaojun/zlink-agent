#!/usr/bin/env python3
"""
YonSuite 配置管理模块

只从环境变量读取配置，禁止在 .env 或任何文件中硬编码真实密钥。
运行时需提前设置环境变量或在 ~/.zshrc / ~/.bashrc 中配置。

配置项（全部从 os.environ 读取）：
- YONSUITE_APP_KEY: App Key
- YONSUITE_APP_SECRET: App Secret
- YONSUITE_TENANT_ID: 租户 ID
- YONSUITE_GATEWAY_URL: API 网关 URL（可选，默认 https://c2.yonyoucloud.com/iuap-api-gateway）
- YONSUITE_TOKEN_URL: Token URL（可选）
- YONSUITE_LOG_LEVEL: 日志级别（可选，默认 INFO）
- YONSUITE_CACHE_DIR: Token 缓存目录（可选）
"""

import os


class Config:
    """YonSuite 配置类 — 只读环境变量，禁止硬编码"""

    # 必需配置（无默认值，必须在运行时设置环境变量）
    APP_KEY: str = os.getenv("YONSUITE_APP_KEY", "")
    APP_SECRET: str = os.getenv("YONSUITE_APP_SECRET", "")
    TENANT_ID: str = os.getenv("YONSUITE_TENANT_ID", "")

    # 可选配置（有默认值）
    GATEWAY_URL: str = os.getenv("YONSUITE_GATEWAY_URL", "https://c2.yonyoucloud.com/iuap-api-gateway")
    TOKEN_URL: str = os.getenv("YONSUITE_TOKEN_URL", "https://c2.yonyoucloud.com/iuap-api-auth")
    DEFAULT_TOKEN_URL: str = os.getenv("YONSUITE_DEFAULT_TOKEN_URL", "https://c2.yonyoucloud.com/iuap-api-auth")

    # 日志配置
    LOG_LEVEL: str = os.getenv("YONSUITE_LOG_LEVEL", "INFO")

    # 缓存配置
    CACHE_DIR: str = os.getenv("YONSUITE_CACHE_DIR", "")

    # Token 缓存提前过期时间（秒）
    TOKEN_REFRESH_BUFFER: int = int(os.getenv("YONSUITE_TOKEN_REFRESH_BUFFER", "300"))

    # HTTP 超时（秒）
    HTTP_TIMEOUT: int = int(os.getenv("YONSUITE_HTTP_TIMEOUT", "30"))

    # 重试配置
    MAX_RETRIES: int = int(os.getenv("YONSUITE_MAX_RETRIES", "3"))
    RETRY_DELAY: float = float(os.getenv("YONSUITE_RETRY_DELAY", "1.0"))

    @classmethod
    def validate(cls) -> None:
        """验证必需配置是否存在"""
        missing = []
        if not os.getenv("YONSUITE_APP_KEY"):
            missing.append("YONSUITE_APP_KEY")
        if not os.getenv("YONSUITE_APP_SECRET"):
            missing.append("YONSUITE_APP_SECRET")
        if not os.getenv("YONSUITE_TENANT_ID"):
            missing.append("YONSUITE_TENANT_ID")

        if missing:
            raise ValueError(
                f"缺少必需的配置项：{', '.join(missing)}\n"
                f"请在 ~/.zshrc 或 ~/.bashrc 中设置环境变量：\n"
                f"  export YONSUITE_APP_KEY=your_app_key\n"
                f"  export YONSUITE_APP_SECRET=your_app_secret\n"
                f"  export YONSUITE_TENANT_ID=your_tenant_id\n"
                f"然后执行: source ~/.zshrc  (或 source ~/.bashrc)"
            )

    @classmethod
    def is_configured(cls) -> bool:
        """检查配置是否完整（实时读取环境变量，支持运行时注入）"""
        return bool(
            os.getenv("YONSUITE_APP_KEY")
            and os.getenv("YONSUITE_APP_SECRET")
            and os.getenv("YONSUITE_TENANT_ID")
        )


# 快捷访问
config = Config()
