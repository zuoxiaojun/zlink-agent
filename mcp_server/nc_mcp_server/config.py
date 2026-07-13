"""NC-MCP 配置管理模块

配置优先级：
1. 进程环境变量（opencode.json mcp.<name>.env 注入）
2. .env 文件（开发调试时用，已 gitignored）
"""

import os
from functools import cached_property

_ENV_LOADED = False


def _ensure_dotenv():
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    pkg_dir = os.path.dirname(os.path.abspath(__file__))
    parts = pkg_dir.split(os.sep)
    for depth in range(len(parts), 0, -1):
        search_dir = os.sep.join(parts[:depth])
        env_path = os.path.join(search_dir, ".env")
        if os.path.isfile(env_path):
            if load_dotenv(dotenv_path=env_path):
                return


class Config:
    """NC-MCP 配置类 — 全部懒加载"""

    # 必需配置
    @cached_property
    def ORACLE_USER(self) -> str:
        return os.getenv("ORACLE_USER", "")

    @cached_property
    def ORACLE_PASSWORD(self) -> str:
        return os.getenv("ORACLE_PASSWORD", "")

    @cached_property
    def ORACLE_HOST(self) -> str:
        return os.getenv("ORACLE_HOST", "")

    @cached_property
    def ORACLE_PORT(self) -> str:
        return os.getenv("ORACLE_PORT", "")

    @cached_property
    def ORACLE_SERVICE(self) -> str:
        return os.getenv("ORACLE_SERVICE", "")

    # 可选配置
    @cached_property
    def MAX_ROWS(self) -> int:
        return int(os.getenv("NC_MCP_MAX_ROWS", "200"))

    @property
    def db_config(self) -> dict:
        """oracledb.connect 参数"""
        port = self.ORACLE_PORT
        if not port:
            raise ValueError(
                "ORACLE_PORT 为空，请检查内置 NC 连接的配置。\n"
                "前往「设置 → ERP → NC」页面填写连接信息即可。"
            )
        return {
            "user": self.ORACLE_USER,
            "password": self.ORACLE_PASSWORD,
            "host": self.ORACLE_HOST,
            "port": int(port),
            "service_name": self.ORACLE_SERVICE,
        }

    def validate(self) -> None:
        """验证必需配置是否存在"""
        missing = []
        for key in ("ORACLE_USER", "ORACLE_PASSWORD", "ORACLE_HOST", "ORACLE_PORT", "ORACLE_SERVICE"):
            if not getattr(self, key):
                missing.append(key)
        if missing:
            raise ValueError(
                f"缺少必需的配置项：{', '.join(missing)}\n"
                "这是内置 NC 数据源，前往「设置 → ERP → NC」页面填写保存即可。"
            )

    @property
    def is_configured(self) -> bool:
        return bool(
            self.ORACLE_USER and self.ORACLE_PASSWORD and self.ORACLE_HOST and self.ORACLE_PORT and self.ORACLE_SERVICE
        )


config = Config()
