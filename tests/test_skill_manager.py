"""Tests for ``agent.skill_manager`` — all skills are always available.

Uses ``tmp_path`` to create temporary skill directories with ``SKILL.md`` files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ── Fixture: redirect skill file paths to tmp_path ─────────────────


@pytest.fixture
def sm(tmp_path: Path, monkeypatch):
    """Return the skill_manager module with all file paths redirected
    to a temp directory."""
    from agent import skill_manager as sm

    # Redirect SKILLS_DIR and USER_SKILLS_DIR in skills_tool
    from agent.tools import skills_tool

    builtin_skills = tmp_path / "skills"
    builtin_skills.mkdir()
    user_skills = tmp_path / "user_skills"
    user_skills.mkdir()

    monkeypatch.setattr(skills_tool, "SKILLS_DIR", builtin_skills)
    monkeypatch.setattr(skills_tool, "USER_SKILLS_DIR", user_skills)

    # Create helper functions that know about the patched dirs
    def patched_find_skill_dir(name):
        u = user_skills / name
        if u.exists() and (u / "SKILL.md").exists():
            return u
        b = builtin_skills / name
        if b.exists() and (b / "SKILL.md").exists():
            return b
        return None

    def patched_get_skill_content(name):
        d = patched_find_skill_dir(name)
        if d is None:
            return None
        md = d / "SKILL.md"
        if md.exists():
            return md.read_text(encoding="utf-8")
        return None

    def patched_load_skill_index():
        skills = []
        for d, is_builtin in skills_tool._get_skill_dirs():
            md = d / "SKILL.md"
            if md.exists():
                raw = md.read_text(encoding="utf-8")
                meta = {}
                if raw.startswith("---"):
                    import yaml

                    try:
                        meta = yaml.safe_load(raw.split("---", 2)[1]) or {}
                    except Exception:
                        meta = {}
                skills.append(
                    {
                        "name": meta.get("name", d.name),
                        "description": meta.get("description", ""),
                        "version": meta.get("version", ""),
                        "tags": meta.get("tags", []),
                        "builtin": is_builtin,
                        "path": str(d),
                    }
                )
        return skills

    # Patch skills_tool module
    monkeypatch.setattr(skills_tool, "_find_skill_dir", patched_find_skill_dir)
    monkeypatch.setattr(skills_tool, "_load_skill_index", patched_load_skill_index)
    monkeypatch.setattr(skills_tool, "_get_skill_content", patched_get_skill_content)

    # skill_manager imports these from skills_tool at module level, so we
    # must also patch the skill_manager module's local references.
    monkeypatch.setattr(sm, "_find_skill_dir", patched_find_skill_dir)
    monkeypatch.setattr(sm, "_load_skill_index", patched_load_skill_index)
    monkeypatch.setattr(sm, "_get_skill_content", patched_get_skill_content)
    monkeypatch.setattr(sm, "SKILLS_DIR", builtin_skills)
    monkeypatch.setattr(sm, "USER_SKILLS_DIR", user_skills)

    return sm, builtin_skills, user_skills


def _create_skill(
    dir_path: Path, name: str, description: str = "", tags: list[str] | None = None, version: str = "1.0"
):
    """Create a skill directory with SKILL.md."""
    skill_dir = dir_path / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    md = skill_dir / "SKILL.md"
    tags_str = f"\ntags: {json.dumps(tags or [])}"
    desc_str = f"\ndescription: {description}" if description else ""
    md.write_text(
        f"---\nname: {name}{desc_str}{tags_str}\nversion: {version}\n---\n\n## Instructions\n\nDo the thing.\n"
    )


# ────────────────────────────────────────────────────────────────────
# 1) Active skills — all skills are always active
# ────────────────────────────────────────────────────────────────────


def test_get_active_skills_returns_all(sm):
    sm_mod, builtin_skills, _ = sm
    _create_skill(builtin_skills, "skill-a")
    _create_skill(builtin_skills, "skill-b")
    active = sm_mod.get_active_skills()
    assert "skill-a" in active
    assert "skill-b" in active


def test_set_skill_active_is_noop(sm):
    sm_mod, builtin_skills, _ = sm
    _create_skill(builtin_skills, "my-skill")
    # All skills are always active — set_skill_active is a no-op
    assert sm_mod.set_skill_active("my-skill", True) is True
    assert sm_mod.set_skill_active("my-skill", False) is True
    assert "my-skill" in sm_mod.get_active_skills()


def test_set_skill_active_unknown_returns_false(sm):
    sm_mod, _, _ = sm
    assert sm_mod.set_skill_active("nonexistent", True) is False


# ────────────────────────────────────────────────────────────────────
# 2) get_all_skills
# ────────────────────────────────────────────────────────────────────


def test_get_all_skills_empty_when_no_skills(sm):
    sm_mod, _, _ = sm
    assert sm_mod.get_all_skills() == []


def test_get_all_skills_returns_builtin_and_user(sm):
    sm_mod, builtin_skills, user_skills = sm
    _create_skill(builtin_skills, "builtin-a", "Built-in A", ["builtin"], "1.0")
    _create_skill(user_skills, "user-a", "User A", ["user"], "2.0")

    all_skills = sm_mod.get_all_skills()
    names = {s["name"] for s in all_skills}
    assert "builtin-a" in names
    assert "user-a" in names


def test_get_all_skills_builtin_flag(sm):
    sm_mod, builtin_skills, user_skills = sm
    _create_skill(builtin_skills, "b1")
    _create_skill(user_skills, "u1")

    all_skills = {s["name"]: s["builtin"] for s in sm_mod.get_all_skills()}
    assert all_skills["b1"] is True
    assert all_skills["u1"] is False


# ────────────────────────────────────────────────────────────────────
# 3) get_skill_content
# ────────────────────────────────────────────────────────────────────


def test_get_skill_content_returns_markdown(sm):
    sm_mod, builtin_skills, _ = sm
    _create_skill(builtin_skills, "doc-skill", "Docs")
    content = sm_mod.get_skill_content("doc-skill")
    assert content is not None
    assert "Instructions" in content
    assert "name: doc-skill" in content


def test_get_skill_content_returns_none_for_unknown(sm):
    sm_mod, _, _ = sm
    assert sm_mod.get_skill_content("unknown") is None


# ────────────────────────────────────────────────────────────────────
# 4) get_skill_index_text (Level 0 injection)
# ────────────────────────────────────────────────────────────────────


def test_get_skill_index_text_empty_when_no_skills(sm):
    sm_mod, _, _ = sm
    assert sm_mod.get_skill_index_text() == ""


def test_get_skill_index_text_mentions_skill(sm):
    sm_mod, builtin_skills, _ = sm
    _create_skill(builtin_skills, "active-one", "The active skill")
    result = sm_mod.get_skill_index_text()
    assert "active-one" in result
    assert "The active skill" in result


def test_get_skill_index_text_includes_tags(sm):
    sm_mod, builtin_skills, _ = sm
    _create_skill(builtin_skills, "tagged", "Has tags", ["python", "data"])
    result = sm_mod.get_skill_index_text()
    assert "python" in result
    assert "data" in result


def test_get_skill_index_text_lists_all_skills(sm):
    sm_mod, builtin_skills, _ = sm
    _create_skill(builtin_skills, "skill-a", "Skill A")
    _create_skill(builtin_skills, "skill-b", "Skill B")
    result = sm_mod.get_skill_index_text()
    assert "skill-a" in result
    assert "skill-b" in result


def test_get_active_instructions_alias(sm):
    """get_active_instructions() is an alias for get_skill_index_text()."""
    sm_mod, builtin_skills, _ = sm
    _create_skill(builtin_skills, "my-skill", "My desc")
    assert sm_mod.get_active_instructions() == sm_mod.get_skill_index_text()


# ────────────────────────────────────────────────────────────────────
# 5) get_instructions_for_query (Level 1 relevance matching)
# ────────────────────────────────────────────────────────────────────


def test_instructions_for_query_empty_no_skills(sm):
    sm_mod, _, _ = sm
    assert sm_mod.get_instructions_for_query("python") == ""


def test_instructions_for_query_no_match(sm):
    sm_mod, builtin_skills, _ = sm
    _create_skill(builtin_skills, "web-dev", "HTML CSS JS", ["frontend"])
    result = sm_mod.get_instructions_for_query("chemistry")
    assert result == ""


def test_instructions_for_query_matches_description(sm):
    sm_mod, builtin_skills, _ = sm
    _create_skill(builtin_skills, "python-dev", "Python programming", ["python"])
    result = sm_mod.get_instructions_for_query("python")
    assert "python-dev" in result
    assert "Do the thing" in result


def test_instructions_for_query_matches_name(sm):
    sm_mod, builtin_skills, _ = sm
    _create_skill(builtin_skills, "data-viz", "Charts", ["visualization"])
    result = sm_mod.get_instructions_for_query("viz")
    # "viz" is in tags[0] → should match via n-grams
    assert "data-viz" in result


# ────────────────────────────────────────────────────────────────────
# 6) _chinese_keywords
# ────────────────────────────────────────────────────────────────────


def test_chinese_keywords_extracts_bigrams():
    from agent.skill_manager import _chinese_keywords

    result = _chinese_keywords("数据分析")
    assert len(result) >= 1
    assert "数据" in result
    assert "分析" in result
    assert "数据分析" in result or "据分" in result


def test_chinese_keywords_handles_empty():
    from agent.skill_manager import _chinese_keywords

    assert _chinese_keywords("") == set()


def test_chinese_keywords_skips_short():
    from agent.skill_manager import _chinese_keywords

    assert _chinese_keywords("a") == set()


# ────────────────────────────────────────────────────────────────────
# 7) install_skill_from_zip
# ────────────────────────────────────────────────────────────────────


def test_install_skill_from_zip(sm, tmp_path):
    sm_mod, _, user_skills = sm
    import zipfile

    zip_path = tmp_path / "test_skill.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("my-skill/SKILL.md", "---\nname: my-skill\n---\n\nContent")

    name = sm_mod.install_skill_from_zip(zip_path)
    assert name == "my-skill"
    assert (user_skills / "my-skill" / "SKILL.md").exists()


def test_install_skill_returns_none_for_no_skill_md(sm, tmp_path):
    sm_mod, _, _ = sm
    import zipfile

    zip_path = tmp_path / "no_skill.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("README.txt", "no skill here")

    result = sm_mod.install_skill_from_zip(zip_path)
    assert result is None


# ────────────────────────────────────────────────────────────────────
# 8) update_skill_content
# ────────────────────────────────────────────────────────────────────


def test_update_skill_content_builtin_returns_none(sm):
    sm_mod, builtin_skills, _ = sm
    _create_skill(builtin_skills, "builtin-one")
    result = sm_mod.update_skill_content("builtin-one", "---\nname: builtin-one\n---\n\nNew")
    assert result is None  # builtin


def test_update_skill_content_user_returns_true(sm):
    sm_mod, _, user_skills = sm
    _create_skill(user_skills, "user-one", "Original")
    result = sm_mod.update_skill_content("user-one", "---\nname: user-one\n---\n\nUpdated")
    assert result is True
    content = sm_mod.get_skill_content("user-one")
    assert "Updated" in content


def test_update_skill_content_invalid_yaml_returns_false(sm):
    sm_mod, _, user_skills = sm
    _create_skill(user_skills, "user-two")
    result = sm_mod.update_skill_content("user-two", "no frontmatter here")
    assert result is False


def test_update_skill_content_missing_name_in_frontmatter_returns_false(sm):
    sm_mod, _, user_skills = sm
    _create_skill(user_skills, "user-three")
    result = sm_mod.update_skill_content("user-three", "---\ndescription: no name\n---\n\nBody")
    assert result is False


# ────────────────────────────────────────────────────────────────────
# 9) uninstall_skill
# ────────────────────────────────────────────────────────────────────


def test_uninstall_skill_builtin_returns_none(sm):
    sm_mod, builtin_skills, _ = sm
    _create_skill(builtin_skills, "builtin-del")
    assert sm_mod.uninstall_skill("builtin-del") is None


def test_uninstall_skill_user_returns_true(sm):
    sm_mod, _, user_skills = sm
    _create_skill(user_skills, "user-del")
    assert sm_mod.uninstall_skill("user-del") is True
    # Still "active" (all skills are active) but directory is gone
    assert "user-del" not in sm_mod.get_active_skills()


def test_uninstall_skill_not_found_returns_false(sm):
    sm_mod, _, _ = sm
    assert sm_mod.uninstall_skill("does-not-exist") is False
