"""Skills REST API — wraps skill_manager."""

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from agent import skill_manager
from backend.schemas.skill import SkillInfo, SkillToggle

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("", response_model=list[SkillInfo])
def list_skills():
    skills = skill_manager.get_all_skills()
    active = set(skill_manager.get_active_skills())
    return [
        SkillInfo(
            name=s["name"],
            description=s.get("description", ""),
            version=s.get("version", ""),
            tags=s.get("tags", []),
            active=s["name"] in active,
        )
        for s in skills
    ]


@router.get("/{name}")
def get_skill(name: str):
    content = skill_manager.get_skill_content(name)
    if content is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"name": name, "content": content}


@router.put("/{name}/toggle")
def toggle_skill(name: str, body: SkillToggle):
    ok = skill_manager.set_skill_active(name, body.active)
    if not ok:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"ok": True}


@router.delete("/{name}")
def delete_skill(name: str):
    ok = skill_manager.uninstall_skill(name)
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
