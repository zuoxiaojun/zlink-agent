"""ERP 工具暴露门控测试。

设计契约（见 AGENTS.md「ERP isolation」）：只有 enabled=true 的 ERP
系统的内置工具才注册进 LLM 工具列表；禁用的系统对 LLM 不可见。

门控实现：erp_nc_tools / erp_ys_tools 注册时带 check_fn，
registry.get_definitions() 在生成 OpenAI 格式工具定义时逐个执行，
因此开关翻转即时生效、无需重新注册。
"""

from __future__ import annotations

import agent.tools.erp_nc_tools  # noqa: F401 — 模块级注册 NC 工具（整个测试会话注册一次即可）
import agent.tools.erp_ys_tools  # noqa: F401 — 模块级注册 YonSuite 工具
from agent.tools.registry import registry

NC_TOOLS = {"nc_query", "nc_list_tables", "nc_describe_table", "nc_raw_sql"}
YS_TOOLS = {"ys_api", "query_sale_orders", "query_purchase_orders"}


def _set_erp_enabled(name: str, enabled: bool) -> None:
    from agent import config_manager

    cfg = config_manager.load()
    erp_clients = dict(cfg.erp_clients or {})
    ecfg = dict(erp_clients.get(name, {}))
    ecfg["enabled"] = enabled
    erp_clients[name] = ecfg
    cfg.erp_clients = erp_clients
    config_manager.save(cfg)


def _definition_names() -> set[str]:
    return {d["function"]["name"] for d in registry.get_definitions()}


def test_nc_tools_hidden_when_disabled(isolated_config):
    _set_erp_enabled("nc", False)
    assert not (NC_TOOLS & _definition_names())


def test_nc_tools_visible_when_enabled(isolated_config):
    _set_erp_enabled("nc", True)
    assert NC_TOOLS <= _definition_names()


def test_yonsuite_tools_hidden_when_disabled(isolated_config):
    _set_erp_enabled("yonsuite", False)
    assert not (YS_TOOLS & _definition_names())


def test_yonsuite_tools_visible_when_enabled(isolated_config):
    _set_erp_enabled("yonsuite", True)
    assert YS_TOOLS <= _definition_names()


def test_erp_toggle_takes_effect_without_reregister(isolated_config):
    """开关翻转不需要重新注册工具——check_fn 每次 get_definitions 时重新读配置。"""
    _set_erp_enabled("nc", True)
    assert NC_TOOLS <= _definition_names()
    _set_erp_enabled("nc", False)
    assert not (NC_TOOLS & _definition_names())
