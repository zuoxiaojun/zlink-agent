"""Skills management tools for ZLink Agent.

Port of Hermes skill system — loads SKILL.md files from the skills directory.
"""

import logging
import re
from pathlib import Path

import yaml

from agent.tools.registry import registry, tool_error, tool_result
from agent.utils import DATA_DIR, atomic_json_write

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"
USER_SKILLS_DIR = DATA_DIR / "skills"
USER_SKILLS_DIR = DATA_DIR / "skills"


def _get_skill_dirs() -> list[tuple[Path, bool]]:
    """Return [(path, is_builtin)] for all skill directories across both locations."""
    dirs = []
    if SKILLS_DIR.exists():
        for entry in sorted(SKILLS_DIR.iterdir()):
            if entry.is_dir() and (entry / "SKILL.md").exists():
                dirs.append((entry, True))
    if USER_SKILLS_DIR.exists():
        for entry in sorted(USER_SKILLS_DIR.iterdir()):
            if entry.is_dir() and (entry / "SKILL.md").exists():
                dirs.append((entry, False))
    return dirs


def _load_skill_index() -> list[dict]:
    """Scan skills directory and return metadata for all available skills."""
    skills = []
    for entry, builtin in _get_skill_dirs():
        skill_file = entry / "SKILL.md"
        try:
            content = skill_file.read_text(encoding="utf-8")
            meta = _parse_frontmatter(content)
            skills.append(
                {
                    "name": meta.get("name", entry.name),
                    "description": meta.get("description", ""),
                    "version": meta.get("version", "1.0.0"),
                    "tags": meta.get("metadata", {}).get("hermes", {}).get("tags", []),
                    "path": str(skill_file),
                    "builtin": builtin,
                }
            )
        except Exception as e:
            logger.warning("Failed to load skill %s: %s", entry.name, e)
    return skills


def _parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from SKILL.md content."""
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}


def _get_skill_content(name: str) -> str | None:
    """Get the full content (frontmatter + body) of a skill by name."""
    for entry, _builtin in _get_skill_dirs():
        if entry.name != name:
            skill_file = entry / "SKILL.md"
            if skill_file.exists():
                meta = _parse_frontmatter(skill_file.read_text(encoding="utf-8"))
                if meta.get("name") == name:
                    return skill_file.read_text(encoding="utf-8")
            continue
        skill_file = entry / "SKILL.md"
        if skill_file.exists():
            return skill_file.read_text(encoding="utf-8")
    return None


def _handle_skill_list(args: dict) -> str:
    """List all available skills."""
    skills = _load_skill_index()
    if not skills:
        return tool_result(data="暂无可用技能。", skills=[])
    return tool_result(
        data=f"发现 {len(skills)} 个可用技能：",
        skills=skills,
    )


def _handle_skill_view(args: dict) -> str:
    """View the full content of a skill."""
    name = args.get("name", "")
    if not name:
        return tool_error("name is required")

    content = _get_skill_content(name)
    if content is None:
        return tool_error(f"未找到技能: {name}")

    # Strip frontmatter for display, keep body
    if content.startswith("---"):
        parts = content.split("---", 2)
        body = parts[2].strip() if len(parts) >= 3 else content
    else:
        body = content

    return tool_result(data=f"# {name}\n\n{body}")


def _load_active_skills() -> list[str]:
    """Read active skill names from persistent file."""
    path = DATA_DIR / "active_skills.json"
    if not path.exists():
        return []
    try:
        import json

        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_active_skills(names: list[str]):
    """Persist active skill names."""
    path = DATA_DIR / "active_skills.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_json_write(path, names)


def _handle_skill_activate(args: dict) -> str:
    """Enable a skill so its instructions are injected into the agent prompt."""
    name = args.get("name", "")
    if not name:
        return tool_error("name is required")
    skills = _load_skill_index()
    if not any(s["name"] == name for s in skills):
        return tool_error(f"未找到技能: {name}")
    active = _load_active_skills()
    if name not in active:
        active.append(name)
        _save_active_skills(active)
    return tool_result(data=f"✅ 已启用技能「{name}」，其指令将在后续对话中生效。")


def _handle_skill_deactivate(args: dict) -> str:
    """Disable a skill, removing its instructions from the agent prompt."""
    name = args.get("name", "")
    if not name:
        return tool_error("name is required")
    active = _load_active_skills()
    if name in active:
        active.remove(name)
        _save_active_skills(active)
    return tool_result(data=f"已停用技能「{name}」。")


SKILL_LIST_SCHEMA = {
    "name": "skill_list",
    "description": "列出所有可用技能的清单（名称 + 简介）。需要完整内容请调用 skill_view。",
    "parameters": {
        "type": "object",
        "properties": {},
    },
}

SKILL_VIEW_SCHEMA = {
    "name": "skill_view",
    "description": "查看指定技能的完整指令。当系统提示中列出的技能与当前任务相关时，调用此工具加载其详细内容。",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "技能名称"},
        },
        "required": ["name"],
    },
}

registry.register(
    name="skill_list",
    toolset="skills",
    schema=SKILL_LIST_SCHEMA,
    handler=_handle_skill_list,
    emoji="📋",
)

SKILL_ACTIVATE_SCHEMA = {
    "name": "skill_activate",
    "description": "启用一个技能，将其指令注入到系统提示中，指导 AI 的行为。",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "要启用的技能名称"},
        },
        "required": ["name"],
    },
}

SKILL_DEACTIVATE_SCHEMA = {
    "name": "skill_deactivate",
    "description": "停用一个技能，从系统提示中移除其指令。",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "要停用的技能名称"},
        },
        "required": ["name"],
    },
}

registry.register(
    name="skill_view",
    toolset="skills",
    schema=SKILL_VIEW_SCHEMA,
    handler=_handle_skill_view,
    emoji="📖",
)

registry.register(
    name="skill_activate",
    toolset="skills",
    schema=SKILL_ACTIVATE_SCHEMA,
    handler=_handle_skill_activate,
    emoji="✅",
)

registry.register(
    name="skill_deactivate",
    toolset="skills",
    schema=SKILL_DEACTIVATE_SCHEMA,
    handler=_handle_skill_deactivate,
    emoji="❌",
)


_SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_MAX_CONTENT_LEN = 100_000


def _validate_skill_name(name: str) -> str | None:
    """Validate skill name format. Returns error message or None."""
    if len(name) > 64:
        return "技能名称不能超过 64 个字符"
    if not _SKILL_NAME_RE.match(name):
        return "技能名称只能包含小写字母、数字、连字符、点、下划线，且必须以字母或数字开头"
    return None


def _find_skill_dir(name: str) -> Path | None:
    """Find skill directory by name in either builtin or user dirs."""
    for entry, _ in _get_skill_dirs():
        if entry.name == name:
            return entry
        skill_file = entry / "SKILL.md"
        if skill_file.exists():
            meta = _parse_frontmatter(skill_file.read_text(encoding="utf-8"))
            if meta.get("name") == name:
                return entry
    return None


def _handle_skill_install(args: dict) -> str:
    """Install a new skill from provided content."""
    name = args.get("name", "").strip().lower()
    content = args.get("content", "").strip()
    files = args.get("files", {})

    if not name:
        return tool_error("skill name is required")
    if not content:
        return tool_error("skill content is required")

    # Validate name format
    err = _validate_skill_name(name)
    if err:
        return tool_error(err)

    # Parse & validate frontmatter
    meta = _parse_frontmatter(content)
    skill_name = meta.get("name", "")
    if not skill_name:
        return tool_error("SKILL.md frontmatter 缺少 name 字段")
    if not meta.get("description", ""):
        return tool_error("SKILL.md frontmatter 缺少 description 字段")
    if meta.get("name") != name:
        name = skill_name

    # Content size check
    if len(content) > _MAX_CONTENT_LEN:
        return tool_error(f"SKILL.md 内容超过 100KB 限制（当前 {len(content)} 字符）")

    # Security scan on SKILL.md body (strip frontmatter)
    body = content.split("---", 2)[2].strip() if content.count("---") >= 2 else content
    from agent.fact_memory import _scan_content as _scan_threats

    scan_err = _scan_threats(body)
    if scan_err:
        return tool_error(f"安全扫描未通过: {scan_err}")

    # Security scan on extra files
    for filename, file_content in files.items():
        fc = file_content.strip()
        ferr = _scan_threats(fc)
        if ferr:
            return tool_error(f"文件「{filename}」安全扫描未通过: {ferr}")

    existing = _find_skill_dir(name)
    if existing:
        return tool_error(f"技能「{name}」已存在，如需覆盖请先停用并删除")

    target_dir = USER_SKILLS_DIR / name
    target_dir.mkdir(parents=True, exist_ok=True)

    tmp = target_dir / "SKILL.md.tmp"
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(target_dir / "SKILL.md")

    written = []
    for filename, file_content in files.items():
        safe_name = Path(filename).name
        if not safe_name:
            continue
        fpath = target_dir / safe_name
        ftmp = target_dir / (safe_name + ".tmp")
        ftmp.write_text(file_content, encoding="utf-8")
        ftmp.replace(fpath)
        written.append(safe_name)

    active = _load_active_skills()
    if name not in active:
        active.append(name)
        _save_active_skills(active)

    parts = [f"✅ 技能「{name}」安装成功并已启用"]
    if written:
        parts.append(f"附带文件: {', '.join(written)}")
    return tool_result(data="\n".join(parts))


SKILL_INSTALL_SCHEMA = {
    "name": "skill_install",
    "description": "安装一个新技能。提供技能名称、SKILL.md 完整内容（含 YAML frontmatter）和可选的附属文件。安装后会自动启用。",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "技能名称，用于目录命名",
            },
            "content": {
                "type": "string",
                "description": "SKILL.md 完整内容，必须以 --- 开头的 YAML frontmatter",
            },
            "files": {
                "type": "object",
                "description": '可选附属文件字典 {文件名: 文件内容}，如 {"techniques.md": "..."}',
                "additionalProperties": {"type": "string"},
            },
        },
        "required": ["name", "content"],
    },
}

registry.register(
    name="skill_install",
    toolset="skills",
    schema=SKILL_INSTALL_SCHEMA,
    handler=_handle_skill_install,
    emoji="📦",
)


# ── Export tool ──────────────────────────────────────────────


def _handle_skill_export(args: dict) -> str:
    """Export a skill as a downloadable SKILL.md file content."""
    name = args.get("name", "")
    if not name:
        return tool_error("name is required")
    content = _get_skill_content(name)
    if content is None:
        return tool_error(f"未找到技能: {name}")
    return tool_result(
        data=f"技能「{name}」的内容如下（可保存为 {name}-SKILL.md）：",
        content=content,
    )


SKILL_EXPORT_SCHEMA = {
    "name": "skill_export",
    "description": "导出指定技能的 SKILL.md 内容，包含完整 frontmatter。可用于备份或分享。",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "要导出的技能名称"},
        },
        "required": ["name"],
    },
}

registry.register(
    name="skill_export",
    toolset="skills",
    schema=SKILL_EXPORT_SCHEMA,
    handler=_handle_skill_export,
    emoji="📤",
)
