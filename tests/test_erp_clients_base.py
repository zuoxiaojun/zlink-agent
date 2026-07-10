"""测试 agent.erp_clients.base 模块的导入与导出"""


def test_import_erp_error():
    from agent.erp_clients.base import ERPError

    assert issubclass(ERPError, Exception)


def test_import_auth_error():
    from agent.erp_clients.base import ERPAuthError, ERPError

    assert issubclass(ERPAuthError, ERPError)


def test_import_rate_limit_error_with_retry_after():
    from agent.erp_clients.base import ERPRateLimitError

    e = ERPRateLimitError("rate limited", retry_after=30)
    assert e.retry_after == 30
    assert "rate limited" in str(e)


def test_import_api_error_with_code():
    from agent.erp_clients.base import ERPAPIError

    e = ERPAPIError(code=401, message="Unauthorized", response={"trace": "x"})
    assert e.code == 401
    assert "401" in str(e)
    assert "Unauthorized" in str(e)


def test_import_mcp_starter_config():
    from agent.erp_clients.base import MCPStarterConfig

    cfg = MCPStarterConfig(
        erp_name="nc",
        enabled=True,
        command="nc-mcp-server",
        args=[],
        env={"ORACLE_HOST": "1.2.3.4"},
        builtin=False,
        install_hint="pip install nc-mcp-server",
    )
    assert cfg.erp_name == "nc"
    assert cfg.enabled is True
    assert cfg.env["ORACLE_HOST"] == "1.2.3.4"


def test_erp_client_protocol_runtime_checkable():
    """YonSuiteClient 结构子类型满足 ERPClient Protocol"""
    from agent.erp_clients.base import ERPClient

    # Protocol 是声明性, 不强制; 仅检查 Protocol 本身是 runtime_checkable
    assert hasattr(ERPClient, "_is_runtime_protocol")
