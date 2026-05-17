"""Memory REST API — read-only views of fact_memory.json and memory.json."""

import json
from fastapi import APIRouter
from agent.utils import DATA_DIR
from agent import memory_manager

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("/facts")
def get_facts():
    fact_path = DATA_DIR / "fact_memory.json"
    if fact_path.exists():
        try:
            data = json.loads(fact_path.read_text(encoding="utf-8"))
            return {"memory": data.get("memory", []), "user": data.get("user", [])}
        except Exception:
            pass
    return {"memory": [], "user": []}


@router.get("/summaries")
def get_summaries():
    mem_path = DATA_DIR / "memory" / "memory.json"
    if mem_path.exists():
        try:
            data = json.loads(mem_path.read_text(encoding="utf-8"))
            return data.get("conversations", [])
        except Exception:
            pass
    return []
