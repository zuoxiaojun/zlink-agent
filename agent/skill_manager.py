"""Skill management for ZLink Agent.

All skills are always available — there is no activate/deactivate concept.
"""

import logging
from pathlib import Path

from agent.tools.skills_tool import SKILLS_DIR, USER_SKILLS_DIR, _find_skill_dir, _get_skill_content, _load_skill_index

logger = logging.getLogger(__name__)


def get_all_skills() -> list[dict]:
    """Return metadata for all available skills."""
    return _load_skill_index()


def get_skill_content(name: str) -> str | None:
    """Return full content (frontmatter + body) of a skill by name."""
    return _get_skill_content(name)


def get_active_skills() -> list[str]:
    """Return all available skill names (all skills are always active)."""
    return [s["name"] for s in _load_skill_index()]


def set_skill_active(name: str, active: bool) -> bool:
    """All skills are always active; this is a no-op."""
    return any(s["name"] == name for s in _load_skill_index())


# ── Prompt injection ──────────────────────────────────────────


def get_skill_index_text() -> str:
    """Build a lightweight skill index for system-prompt injection.

    Returns all skill names + descriptions. The agent uses `skill_view`
    to load full instructions on demand.
    ERP 技能（nc/u8/yonsuite-skill）仅在其对应 ERP 启用时显示。
    """
    index = _load_skill_index()
    if not index:
        return ""

    # ERP 技能 → 配置键映射
    _erp_skill_map = {
        "nc": "nc",
        "u8": "u8",
        "u9c": "u9c",
        "yonsuite-skill": "yonsuite",
    }

    def _erp_enabled(skill_name: str) -> bool:
        erp_key = _erp_skill_map.get(skill_name)
        if erp_key is None:
            return True  # 非 ERP 技能始终显示
        try:
            from agent import config_manager

            cfg = config_manager.load()
            ecfg = cfg.erp_clients.get(erp_key, {})
            return bool(ecfg.get("enabled", False)) if isinstance(ecfg, dict) else False
        except Exception:
            return True  # 读取失败时保守显示

    lines = []
    for s in index:
        name = s["name"]
        if not _erp_enabled(name):
            continue
        desc = s.get("description", "")
        parts = [f"- **{name}**"]
        if desc:
            parts.append(f": {desc}")
        if s.get("tags"):
            parts.append(f" `[{', '.join(s['tags'])}]`")
        lines.append("".join(parts))

    return (
        "\n\n## 可用技能\n\n"
        "你拥有以下技能。当用户的问题涉及某个技能领域时，"
        "使用 `skill_view` 加载该技能的完整指令并严格遵循：\n\n" + "\n".join(lines)
    )


# ── Backward-compatible aliases ───────────────────────────────


def get_active_instructions() -> str:
    """Alias for get_skill_index_text()."""
    return get_skill_index_text()


# ── Relevance-based auto loading ─────────────────────────────


def _chinese_keywords(text: str) -> set[str]:
    """Extract meaningful 2+ character segments from Chinese/mixed text."""
    results = set()
    cleaned = text.lower().strip()
    if len(cleaned) >= 2:
        results.add(cleaned)
    for i in range(len(cleaned) - 1):
        chunk = cleaned[i : i + 2]
        if chunk.isalnum() or any("一" <= c <= "鿿" for c in chunk):
            results.add(chunk)
    return results


def get_instructions_for_query(query: str) -> str:
    """Return full skill instructions for skills relevant to the user's query.

    Uses n-gram keyword matching against skill name, description, and tags.
    Skills whose metadata overlaps with the query get their full body loaded.
    ERP 技能（nc/u8/yonsuite-skill）仅在其对应 ERP 启用时加载。
    """
    if not query:
        return ""

    # ERP 技能 → 配置键映射
    _erp_skill_map = {
        "nc": "nc",
        "u8": "u8",
        "u9c": "u9c",
        "yonsuite-skill": "yonsuite",
    }

    def _erp_enabled(skill_name: str) -> bool:
        erp_key = _erp_skill_map.get(skill_name)
        if erp_key is None:
            return True
        try:
            from agent import config_manager

            cfg = config_manager.load()
            ecfg = cfg.erp_clients.get(erp_key, {})
            return bool(ecfg.get("enabled", False)) if isinstance(ecfg, dict) else False
        except Exception:
            return True

    query_ngrams = _chinese_keywords(query)
    index = _load_skill_index()
    matched = []

    for s in index:
        name = s["name"]
        if not _erp_enabled(name):
            continue
        text = f"{name} {s.get('description', '')} {' '.join(s.get('tags', []))}"
        skill_ngrams = _chinese_keywords(text)
        if not query_ngrams or query_ngrams & skill_ngrams:
            content = _get_skill_content(name)
            if content:
                if content.startswith("---"):
                    body = content.split("---", 2)[2].strip() if content.count("---") >= 2 else content
                else:
                    body = content.strip()
                if body:
                    matched.append(f"## {name}\n\n{body}")

    if not matched:
        return ""

    return "\n\n## 触发技能指令\n\n根据你的问题，以下技能与之相关，请严格遵循：\n\n" + "\n\n".join(matched)


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