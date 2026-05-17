"""YS-Agent FastAPI backend — serves REST API + WebSocket for the React frontend."""

import logging
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so agent/ imports work
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import CORS_ORIGINS
from agent.utils import DATA_DIR

# Logging setup
_LOG_DIR = DATA_DIR / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(str(_LOG_DIR / "app.log"), encoding="utf-8"),
    ],
    force=True,
)

app = FastAPI(title="YS-Agent API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    from agent.utils import DATA_DIR
    from agent import search_index

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    search_index.init_db()
    if search_index.count_indexed() == 0:
        n = search_index.migrate_from_json()
        if n:
            import logging
            logging.getLogger(__name__).info("搜索索引迁移完成: %d 个会话", n)


# Register routers
from backend.api.sessions import router as sessions_router
from backend.api.config_api import router as config_router
from backend.api.memory_api import router as memory_router
from backend.api.skills_api import router as skills_router
from backend.api.tools_api import router as tools_router
from backend.api.chat import router as chat_router

app.include_router(sessions_router)
app.include_router(config_router)
app.include_router(memory_router)
app.include_router(skills_router)
app.include_router(tools_router)
app.include_router(chat_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
