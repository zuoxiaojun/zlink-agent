"""测试 config_manager 的 erp_clients 支持 + 占位符解析"""


def test_get_erp_config_existing(tmp_path, monkeypatch):
    """erp_clients 段存在时, get_erp_config 返回该 ERP 的配置"""
    from agent import config_manager

    cfg_file = tmp_path / "config.json"
    cfg_file.write_text('{"erp_clients": {"nc": {"host": "1.2.3.4", "user": "u"}}}')
    monkeypatch.setattr(config_manager, "CONFIG_FILE", cfg_file)

    cfg = config_manager.get_erp_config("nc")
    assert cfg["host"] == "1.2.3.4"
    assert cfg["user"] == "u"


def test_get_erp_config_missing_returns_empty(tmp_path, monkeypatch):
    """erp_clients 段不存在或某个 ERP 不存在时, 返回空 dict"""
    from agent import config_manager

    cfg_file = tmp_path / "config.json"
    cfg_file.write_text("{}")
    monkeypatch.setattr(config_manager, "CONFIG_FILE", cfg_file)

    cfg = config_manager.get_erp_config("nonexistent")
    assert cfg == {}


def test_resolve_placeholders_simple():
    """${nc.host} 占位符解析为实际值"""
    from agent.config_manager import resolve_placeholders

    env = {"ORACLE_HOST": "${nc.host}", "STATIC": "value"}
    config = {"erp_clients": {"nc": {"host": "1.2.3.4"}}}
    result = resolve_placeholders(env, config)
    assert result["ORACLE_HOST"] == "1.2.3.4"
    assert result["STATIC"] == "value"


def test_resolve_placeholders_nested():
    """嵌套路径占位符正确解析"""
    from agent.config_manager import resolve_placeholders

    env = {"ORACLE_USER": "${nc.user}", "ORACLE_PASSWORD": "${nc.password}"}
    config = {"erp_clients": {"nc": {"user": "NC65", "password": "secret"}}}
    result = resolve_placeholders(env, config)
    assert result["ORACLE_USER"] == "NC65"
    assert result["ORACLE_PASSWORD"] == "secret"


def test_resolve_placeholders_missing_keeps_literal():
    """占位符引用不存在路径时, 保留字面量 (启动时报错定位更明确)"""
    from agent.config_manager import resolve_placeholders

    env = {"X": "${nc.missing}"}
    config = {"erp_clients": {"nc": {}}}
    result = resolve_placeholders(env, config)
    # 占位符无法解析时保留原样
    assert result["X"] == "${nc.missing}"


def test_resolve_placeholders_non_string_unchanged():
    """非字符串值不变 (e.g. 数字/布尔)"""
    from agent.config_manager import resolve_placeholders

    env = {"PORT": 1521, "ENABLED": True, "HOST": "${nc.host}"}
    config = {"erp_clients": {"nc": {"host": "1.2.3.4"}}}
    result = resolve_placeholders(env, config)
    assert result["PORT"] == 1521
    assert result["ENABLED"] is True
    assert result["HOST"] == "1.2.3.4"
