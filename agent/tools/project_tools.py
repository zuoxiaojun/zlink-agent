"""Project tools — named workspaces for organizing analysis work.

Projects let users create, switch between, and list named analysis contexts.
Each project is a lightweight record (id, name, description, created_at) stored
in a JSON file under the data directory. The active project can be used to
scope session context and organize related work.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from agent.tools.registry import registry
from agent.utils import DATA_DIR, atomic_json_write

logger = logging.getLogger(__name__)

PROJECTS_FILE = DATA_DIR / "projects.json"

# In-memory cache of active project ID
_active_project_id: str | None = None


def _load_projects() -> list[dict[str, Any]]:
    if not PROJECTS_FILE.exists():
        return []
    try:
        data = json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_projects(projects: list[dict[str, Any]]):
    PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    atomic_json_write(PROJECTS_FILE, projects)


def project_list() -> str:
    """List all projects and identify the active one."""
    projects = _load_projects()
    return json.dumps(
        {
            "active_id": _active_project_id,
            "projects": [
                {
                    "id": p["id"],
                    "name": p["name"],
                    "description": p.get("description", ""),
                    "created_at": p.get("created_at", ""),
                    "active": p["id"] == _active_project_id,
                }
                for p in projects
            ],
        },
        ensure_ascii=False,
    )


def project_create(name: str, description: str = "") -> str:
    """Create a new project and switch to it."""
    name = (name or "").strip()
    if not name:
        return json.dumps({"success": False, "error": "项目名称不能为空"})

    projects = _load_projects()

    # Check duplicate name
    for p in projects:
        if p["name"].lower() == name.lower():
            return json.dumps({"success": False, "error": f"项目 '{name}' 已存在"})

    project_id = uuid4().hex[:12]
    now = datetime.now(UTC).isoformat()
    project = {
        "id": project_id,
        "name": name,
        "description": (description or "").strip(),
        "created_at": now,
    }
    projects.append(project)
    _save_projects(projects)

    global _active_project_id
    _active_project_id = project_id

    return json.dumps(
        {
            "success": True,
            "id": project_id,
            "name": name,
            "description": project["description"],
        },
        ensure_ascii=False,
    )


def project_switch(name_or_id: str) -> str:
    """Switch the active project by name or id."""
    needle = (name_or_id or "").strip()
    if not needle:
        return json.dumps({"success": False, "error": "请指定项目名称或ID"})

    projects = _load_projects()
    # Try exact id, then name, then case-insensitive name
    for p in projects:
        if p["id"] == needle or p["name"] == needle:
            break
        if p["name"].lower() == needle.lower():
            break
    else:
        return json.dumps({"success": False, "error": f"未找到项目 '{needle}'"})

    global _active_project_id
    _active_project_id = p["id"]

    return json.dumps(
        {"success": True, "id": p["id"], "name": p["name"]},
        ensure_ascii=False,
    )


PROJECT_LIST_SCHEMA = {
    "name": "project_list",
    "description": "列出所有分析项目及其状态。",
    "parameters": {"type": "object", "properties": {}},
}

PROJECT_CREATE_SCHEMA = {
    "name": "project_create",
    "description": "创建一个新的分析项目（命名工作区）并切换到该项目。用于开始新的分析课题。",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "项目名称，如 'Q3 销售分析'",
            },
            "description": {
                "type": "string",
                "description": "项目描述（可选）",
            },
        },
        "required": ["name"],
    },
}

PROJECT_SWITCH_SCHEMA = {
    "name": "project_switch",
    "description": "切换到已有的分析项目（按名称或ID）。项目名称区分大小写。",
    "parameters": {
        "type": "object",
        "properties": {
            "name_or_id": {
                "type": "string",
                "description": "项目名称或ID",
            },
        },
        "required": ["name_or_id"],
    },
}

registry.register(
    name="project_list",
    toolset="project",
    schema=PROJECT_LIST_SCHEMA,
    handler=lambda args, **kw: project_list(),
    description="列出所有分析项目",
    emoji="📋",
)

registry.register(
    name="project_create",
    toolset="project",
    schema=PROJECT_CREATE_SCHEMA,
    handler=lambda args, **kw: project_create(
        name=args.get("name", ""),
        description=args.get("description", ""),
    ),
    description="创建新的分析项目",
    emoji="🆕",
    risk_level="low",
)

registry.register(
    name="project_switch",
    toolset="project",
    schema=PROJECT_SWITCH_SCHEMA,
    handler=lambda args, **kw: project_switch(
        name_or_id=args.get("name_or_id", ""),
    ),
    description="切换到已有分析项目",
    emoji="🔄",
)
