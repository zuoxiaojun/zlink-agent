"""Skills REST API — wraps skill_manager."""

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from agent import skill_manager
from backend.schemas.skill import SkillInfo, SkillUpdate

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("", response_model=list[SkillInfo])
def list_skills():
    skills = skill_manager.get_all_skills()
    return [
        SkillInfo(
            name=s["name"],
            description=s.get("description", ""),
            version=s.get("version", ""),
            tags=s.get("tags", []),
            active=True,  # all skills are always active
            builtin=s.get("builtin", False),
        )
        for s in skills
    ]


@router.get("/{name}")
def get_skill(name: str):
    """Get a single skill's SKILL.md content."""
    content = skill_manager.get_skill_content(name)
    if content is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"name": name, "content": content}


@router.put("/{name}")
def update_skill(name: str, body: SkillUpdate):
    ok = skill_manager.update_skill_content(name, body.content)
    if ok is None:
        raise HTTPException(status_code=403, detail="内置技能不允许修改")
    if not ok:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"ok": True}


@router.delete("/{name}")
def delete_skill(name: str):
    ok = skill_manager.uninstall_skill(name)
    if ok is None:
        raise HTTPException(status_code=403, detail="内置技能不允许删除")
    if not ok:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"ok": True}


@router.post("/install")
async def install_skill(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are accepted")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / "skill.zip"
            zip_path.write_bytes(await file.read())
            skill_name = skill_manager.install_skill_from_zip(zip_path)
            if skill_name:
                return {"skill_name": skill_name}
            raise HTTPException(status_code=400, detail="No SKILL.md found in the zip")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
