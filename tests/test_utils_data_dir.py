"""测试 _resolve_data_dir 的解析逻辑 (v1.5.2)"""


def test_zlink_data_dir_env_takes_priority(monkeypatch, tmp_path):
    """ZLINK_DATA_DIR 环境变量优先级最高"""
    monkeypatch.delenv("ZLINK_DATA_DIR", raising=False)
    target = tmp_path / "zlink-env"
    monkeypatch.setenv("ZLINK_DATA_DIR", str(target))
    # 重新 import 以触发 module-level DATA_DIR 重算
    import importlib

    import agent.utils as utils

    importlib.reload(utils)
    assert str(utils._resolve_data_dir()) == str(target.resolve())
