"""cronjob 必须把自己创建的 sid 透传给冻结入口 run_conversation（否则产物无归属）。"""

from agent import config_manager, fact_memory, memory_manager, search_index, skill_manager
from agent import session_manager as sm
from agent.config_model import AppConfig
from agent.tools import cronjob_tools as cj


def test_job_prompt_passes_session_id(tmp_path, monkeypatch):
    root = tmp_path / "sessions"
    root.mkdir()
    monkeypatch.setattr(sm, "SESSIONS_DIR", root)
    monkeypatch.setattr(sm, "INDEX_FILE", root / "index.json")
    monkeypatch.setattr(search_index, "DB_PATH", tmp_path / "search.db")

    cfg = AppConfig(llm_api_key="sk-test", llm_base_url="http://x", llm_model="m")
    monkeypatch.setattr(config_manager, "load", lambda: cfg)
    monkeypatch.setattr(fact_memory, "init_store", lambda *a, **k: None)
    monkeypatch.setattr(memory_manager, "get_context", lambda *a, **k: "")
    monkeypatch.setattr(skill_manager, "get_active_instructions", lambda *a, **k: "")
    monkeypatch.setattr(skill_manager, "get_active_skills", lambda *a, **k: [])

    seen: dict = {}

    class FakeAgent:
        def __init__(self, **kwargs):
            self.system_prompt = kwargs.get("system_prompt", "P")

        def run_conversation(self, **kw):
            seen.update(kw)
            return {
                "final_response": "ok",
                "messages": [],
                "api_calls": 1,
                "token_usage": None,
                "completed": True,
                "error": None,
            }

    import agent.agent as agent_mod

    monkeypatch.setattr(agent_mod, "AIAgent", FakeAgent)

    sid = cj._execute_job_prompt("日报", "生成日报")
    assert sid is not None, "_execute_job_prompt 内部吞异常会返回 None —— 检查桩件是否缺失"
    assert seen.get("session_id") == sid
    assert (root / sid / "artifacts").is_dir()
