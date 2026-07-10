"""测试 _resolve_data_dir 的双兼容逻辑 (v1.5.0)"""


def test_zlink_data_dir_env_takes_priority(monkeypatch, tmp_path):
    """ZLINK_DATA_DIR 环境变量优先级最高"""
    monkeypatch.delenv("ZLINK_DATA_DIR", raising=False)
    monkeypatch.delenv("YS_DATA_DIR", raising=False)
    target = tmp_path / "zlink-env"
    monkeypatch.setenv("ZLINK_DATA_DIR", str(target))
    # 重新 import 以触发 module-level DATA_DIR 重算
    import importlib

    import agent.utils as utils

    importlib.reload(utils)
    assert str(utils._resolve_data_dir()) == str(target.resolve())


def test_ys_data_dir_env_as_fallback(monkeypatch, tmp_path):
    """YS_DATA_DIR 环境变量 (老用法) 兼容"""
    monkeypatch.delenv("ZLINK_DATA_DIR", raising=False)
    monkeypatch.setenv("YS_DATA_DIR", str(tmp_path / "ys-env"))
    import importlib

    import agent.utils as utils

    importlib.reload(utils)
    assert str(utils._resolve_data_dir()) == str((tmp_path / "ys-env").resolve())


def test_zlink_data_dir_preferred_over_ys_data_dir(monkeypatch, tmp_path):
    """ZLINK_DATA_DIR 比 YS_DATA_DIR 优先"""
    monkeypatch.setenv("ZLINK_DATA_DIR", str(tmp_path / "zlink"))
    monkeypatch.setenv("YS_DATA_DIR", str(tmp_path / "ys"))
    import importlib

    import agent.utils as utils

    importlib.reload(utils)
    assert str(utils._resolve_data_dir()) == str((tmp_path / "zlink").resolve())
