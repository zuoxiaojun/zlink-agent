"""Cron job management REST API — wraps cronjob_tools for the frontend."""

import json

from fastapi import APIRouter

from agent.tools.cronjob_tools import cronjob_create, cronjob_delete, cronjob_list, cronjob_run, cronjob_toggle

router = APIRouter(prefix="/api/cronjobs", tags=["cronjobs"])


@router.get("")
def list_cronjobs():
    """List all cron jobs."""
    result = json.loads(cronjob_list())
    return result


@router.post("")
def create_cronjob(body: dict):
    """Create a new cron job."""
    result = json.loads(
        cronjob_create(
            name=body.get("name", ""),
            schedule=body.get("schedule", ""),
            prompt=body.get("prompt", ""),
        )
    )
    if not result.get("success"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=result.get("error", "创建失败"))
    return result


@router.delete("/{job_id}")
def delete_cronjob(job_id: str):
    """Delete a cron job."""
    result = json.loads(cronjob_delete(job_id=job_id))
    if not result.get("success"):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=result.get("error", "未找到"))
    return result


@router.post("/{job_id}/run")
def run_cronjob(job_id: str):
    """Immediately trigger a cron job."""
    result = json.loads(cronjob_run(job_id=job_id))
    if not result.get("success"):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=result.get("error", "未找到"))
    return result


@router.put("/{job_id}/toggle")
def toggle_cronjob(job_id: str, body: dict):
    """Enable or disable a cron job."""
    result = json.loads(
        cronjob_toggle(job_id=job_id, enabled=body.get("enabled", True))
    )
    if not result.get("success"):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=result.get("error", "未找到"))
    return result
