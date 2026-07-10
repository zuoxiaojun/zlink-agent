"""Skill management for ZLink Agent.

Manages skill activation state and builds prompt-injection
instructions from active skills for the agent loop.
"""

import json
import logging
from pathlib import Path

from agent.tools.skills_tool import SKILLS_DIR, USER_SKILLS_DIR, _find_skill_dir, _get_skill_content, _load_skill_index
from agent.utils import DATA_DIR, atomic_json_write

logger = logging.getLogger(__name__)

ACTIVE_SKILLS_FILE = DATA_DIR / "active_skills.json"


# ── Active skills persistence ─────────────────────────────────


def _load_active() -> list[str]:
    if not ACTIVE_SKILLS_FILE.exists():
        return []
    try:
        data = json.loads(ACTIVE_SKILLS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_active(names: list[str]):
    ACTIVE_SKILLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    atomic_json_write(ACTIVE_SKILLS_FILE, names)


def get_all_skills() -> list[dict]:
    """Return metadata for all available skills."""
    return _load_skill_index()


def get_skill_content(name: str) -> str | None:
    """Return full content (frontmatter + body) of a skill by name."""
    return _get_skill_content(name)


def get_active_skills() -> list[str]:
    """Return list of currently active skill names."""
    return _load_active()


def set_skill_active(name: str, active: bool) -> bool:
    """Activate or deactivate a skill. Returns False if skill doesn't exist."""
    all_skills = _load_skill_index()
    if not any(s["name"] == name for s in all_skills):
        return False
    names = _load_active()
    if active and name not in names:
        names.append(name)
        _save_active(names)
    elif not active and name in names:
        names.remove(name)
        _save_active(names)
    return True


# ── Prompt injection ──────────────────────────────────────────


def get_active_instructions() -> str:
    """Build a lightweight skill index for system-prompt injection.

    Follows Hermes Agent's progressive-disclosure pattern:
    only skill names + descriptions are injected (Level 0).
    The agent uses `skill_view` to load full instructions on demand.
    """
    names = _load_active()
    if not names:
        return ""

    index = _load_skill_index()
    lines = []
    for name in names:
        for s in index:
            if s["name"] == name:
                desc = s.get("description", "")
                parts = [f"- **{name}**"]
                if desc:
                    parts.append(f": {desc}")
                if s.get("tags"):
                    parts.append(f" `[{', '.join(s['tags'])}]`")
                lines.append("".join(parts))
                break

    if not lines:
        return ""

    return (
        "\n\n## 已启用的技能\n\n"
        "你已启用以下技能。当用户的问题涉及某个技能领域时，"
        "使用 `skill_view` 加载该技能的完整指令并严格遵循：\n\n" + "\n".join(lines)
    )


# ── Relevance-based auto loading ─────────────────────────────


def _chinese_keywords(text: str) -> set[str]:
    """Extract meaningful 2+ character segments from Chinese/mixed text."""
    results = set()
    cleaned = text.lower().strip()
    # Add the whole text
    if len(cleaned) >= 2:
        results.add(cleaned)
    # Add overlapping 2-char n-grams (covers Chinese without word segmentation)
    for i in range(len(cleaned) - 1):
        chunk = cleaned[i : i + 2]
        if chunk.isalnum() or any("一" <= c <= "鿿" for c in chunk):
            results.add(chunk)
    return results


def get_instructions_for_query(query: str) -> str:
    """Return full skill instructions for skills relevant to the user's query.

    Uses n-gram keyword matching against skill name, description, and tags.
    Skills whose metadata overlaps with the query get their full body loaded (Tier 1).
    """
    names = _load_active()
    if not names or not query:
        return ""

    query_ngrams = _chinese_keywords(query)
    index = _load_skill_index()
    matched = []

    for name in names:
        for s in index:
            if s["name"] != name:
                continue
            text = f"{name} {s.get('description', '')} {' '.join(s.get('tags', []))}"
            skill_ngrams = _chinese_keywords(text)
            # Match if any n-gram overlaps
            if not query_ngrams or query_ngrams & skill_ngrams:
                content = _get_skill_content(name)
                if content:
                    if content.startswith("---"):
                        body = content.split("---", 2)[2].strip() if content.count("---") >= 2 else content
                    else:
                        body = content.strip()
                    if body:
                        matched.append(f"## {name}\n\n{body}")
            break

    if not matched:
        return ""

    return "\n\n## 触发技能指令\n\n根据你的问题，以下已启用的技能与之相关，请严格遵循：\n\n" + "\n\n".join(matched)


# ── Content update ────────────────────────────────────────────


def update_skill_content(name: str, content: str) -> bool | None:
    """Update a skill's SKILL.md content. Returns True/False; None if builtin."""
    target_dir = _find_skill_dir(name)
    if target_dir is None:
        return False
    if target_dir.parent == SKILLS_DIR:
        return None
    import yaml

    skill_file = target_dir / "SKILL.md"
    if not skill_file.exists():
        return False
    if content.startswith("---"):
        try:
            meta = yaml.safe_load(content.split("---", 2)[1])
            if not meta or not meta.get("name"):
                return False
        except yaml.YAMLError:
            return False
    else:
        return False
    tmp = skill_file.with_suffix(".md.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(skill_file)
    logger.info("Skill content updated: %s", name)
    return True


# ── Zip installation ──────────────────────────────────────────


def uninstall_skill(name: str) -> bool | None:
    """Delete a user-installed skill directory. Returns True/False; None if builtin."""
    target_dir = _find_skill_dir(name)
    if target_dir is None:
        return False
    if target_dir.parent == SKILLS_DIR:
        return None
    import shutil

    shutil.rmtree(target_dir)
    active = _load_active()
    if name in active:
        active.remove(name)
        _save_active(active)
    logger.info("Skill uninstalled: %s", name)
    return True


def install_skill_from_zip(zip_path: Path) -> str | None:
    """Extract & install a skill from a zip archive. Returns skill name or None."""
    import shutil
    import tempfile
    import zipfile

    import yaml

    try:
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(zip_path, "r") as zf:
                skill_mds = [n for n in zf.namelist() if n.endswith("SKILL.md")]
                if not skill_mds:
                    return None
                zf.extractall(tmp)
                for rel in skill_mds:
                    parent = Path(rel).parent
                    skill_dir = Path(tmp) / parent
                    md_path = skill_dir / "SKILL.md"
                    raw = md_path.read_text(encoding="utf-8")
                    meta = yaml.safe_load(raw.split("---", 2)[1]) if raw.startswith("---") else {}
                    meta_name = meta.get("name", parent.name if parent.name != "." else "unknown")
                    target = USER_SKILLS_DIR / meta_name
                    shutil.rmtree(target, ignore_errors=True)
                    shutil.copytree(skill_dir, target)
                    logger.info("Skill installed: %s", meta_name)
                    return meta_name
            return None
    except Exception:
        logger.exception("Skill install failed")
        raise
