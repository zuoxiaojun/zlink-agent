"""Cron job management tools for ZLink Agent.

Lets the LLM create, list, pause, resume, and remove scheduled tasks.
Jobs are stored as JSON in data/jobs/ and checked by a background scheduler
thread. When a job fires, the configured prompt is sent as a user message
to the AI agent (triggering whatever tools/skills the prompt requires).
"""

import json
import logging
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from agent.tools.registry import registry, tool_error, tool_result
from agent.utils import DATA_DIR

logger = logging.getLogger(__name__)

JOBS_DIR = DATA_DIR / "jobs"
JOBS_FILE = JOBS_DIR / "jobs.json"

# ── Scheduler ────────────────────────────────────────────────────────────

_scheduler_thread: threading.Thread | None = None
_scheduler_stop = threading.Event()
_scheduler_lock = threading.Lock()


def _ensure_jobs_file():
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    if not JOBS_FILE.exists():
        JOBS_FILE.write_text("[]", encoding="utf-8")


def _load_jobs() -> list[dict[str, Any]]:
    _ensure_jobs_file()
    try:
        return json.loads(JOBS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_jobs(jobs: list[dict[str, Any]]):
    _ensure_jobs_file()
    from agent.utils import atomic_json_write

    atomic_json_write(JOBS_FILE, jobs)


def _next_run(schedule: str) -> str | None:
    """Parse a cron-like schedule and return the next run timestamp.

    Supports:
      - "every N minutes/hours/days"
      - "every day at HH:MM"
      - ISO 8601 timestamp (one-shot at that time)
    """
    s = schedule.strip().lower()

    # ISO 8601 one-shot
    try:
        dt = datetime.fromisoformat(s)
        if dt > datetime.now(timezone.utc):
            return dt.isoformat()
    except ValueError:
        pass

    # "every N minutes|hours|days"
    m = re.match(r"every\s+(\d+)\s*(min(?:ute)?s?|hour(?:s)?|day(?:s)?)", s)
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        now = datetime.now(timezone.utc)
        if unit.startswith("min"):
            next_dt = now + timedelta(minutes=num)
        elif unit.startswith("hour"):
            next_dt = now + timedelta(hours=num)
        else:
            next_dt = now + timedelta(days=num)
        return next_dt.isoformat()

    # "every day at HH:MM" or "daily at HH:MM"
    m = re.match(r"(?:every\s+day|daily)\s+at\s+(\d{1,2}):(\d{2})", s)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        now = datetime.now(timezone.utc)
        next_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_dt <= now:
            next_dt += timedelta(days=1)
        return next_dt.isoformat()

    return None


def _scheduler_loop():
    """Background loop that checks for due jobs every 30 seconds."""
    while not _scheduler_stop.is_set():
        try:
            _check_and_fire_jobs()
        except Exception as e:
            logger.exception("Cron scheduler error: %s", e)
        _scheduler_stop.wait(30)


def _check_and_fire_jobs():
    """Find due jobs, execute them through the AI, and save results as sessions."""
    now = datetime.now(timezone.utc)
    jobs = _load_jobs()
    changed = False

    for job in jobs:
        if not job.get("enabled", True):
            continue
        next_run = job.get("next_run_at")
        if not next_run:
            continue
        try:
            run_at = datetime.fromisoformat(next_run)
            if run_at <= now:
                name = job.get("name", "")
                prompt = job.get("prompt", "")
                job_id = job.get("id", "")

                logger.info("Cron job '%s' (id=%s) fired at %s", name, job_id, now.isoformat())

                # Execute the actual job
                session_id = _execute_job_prompt(name, prompt)
                job["last_run_at"] = now.isoformat()
                job["last_status"] = "completed" if session_id else "failed"
                job["last_session_id"] = session_id

                # Calculate next run
                schedule = job.get("schedule", "")
                if schedule.startswith("every") or schedule.startswith("daily"):
                    next_nr = _next_run(schedule)
                    if next_nr:
                        job["next_run_at"] = next_nr
                    else:
                        job["next_run_at"] = (now + timedelta(days=1)).isoformat()
                else:
                    job["enabled"] = False
                    job["next_run_at"] = None

                changed = True
        except (ValueError, TypeError):
            continue

    if changed:
        _save_jobs(jobs)


def start_scheduler():
    """Start the background cron scheduler (idempotent)."""
    global _scheduler_thread
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        return
    _scheduler_stop.clear()
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True, name="cron-scheduler")
    _scheduler_thread.start()
    logger.info("Cron scheduler started")


def stop_scheduler():
    """Stop the background cron scheduler."""
    _scheduler_stop.set()
    global _scheduler_thread
    if _scheduler_thread:
        _scheduler_thread.join(timeout=5)
        _scheduler_thread = None
    logger.info("Cron scheduler stopped")


# ── Tool handlers ────────────────────────────────────────────────────────


def cronjob_list() -> str:
    """List all cron jobs."""
    jobs = _load_jobs()
    return json.dumps(
        {
            "jobs": [
                {
                    "id": j.get("id"),
                    "name": j.get("name", ""),
                    "schedule": j.get("schedule", ""),
                    "prompt": j.get("prompt", ""),
                    "enabled": j.get("enabled", True),
                    "last_run_at": j.get("last_run_at"),
                    "last_status": j.get("last_status"),
                    "last_session_id": j.get("last_session_id"),
                    "next_run_at": j.get("next_run_at"),
                    "created_at": j.get("created_at"),
                }
                for j in jobs
            ],
            "total": len(jobs),
        },
        ensure_ascii=False,
    )


def cronjob_create(name: str, schedule: str, prompt: str) -> str:
    """Create a new cron job."""
    name = (name or "").strip()
    schedule = (schedule or "").strip()
    prompt = (prompt or "").strip()

    if not name:
        return json.dumps({"success": False, "error": "任务名称不能为空"})
    if not schedule:
        return json.dumps({"success": False, "error": "调度表达式不能为空"})
    if not prompt:
        return json.dumps({"success": False, "error": "任务提示词不能为空"})

    # Validate schedule
    next_nr = _next_run(schedule)
    if next_nr is None:
        return json.dumps({
            "success": False,
            "error": f"无法解析调度表达式: '{schedule}'。支持格式：'every N minutes/hours/days'、'every day at HH:MM'、ISO时间戳",
        })

    job_id = uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    job = {
        "id": job_id,
        "name": name,
        "schedule": schedule,
        "prompt": prompt,
        "enabled": True,
        "next_run_at": next_nr,
        "last_run_at": None,
        "last_status": None,
        "created_at": now,
    }

    jobs = _load_jobs()
    jobs.append(job)
    _save_jobs(jobs)

    return json.dumps(
        {
            "success": True,
            "id": job_id,
            "name": name,
            "next_run_at": next_nr,
        },
        ensure_ascii=False,
    )


def cronjob_delete(job_id: str) -> str:
    """Delete a cron job by id."""
    jobs = _load_jobs()
    before = len(jobs)
    jobs = [j for j in jobs if j.get("id") != job_id]
    if len(jobs) == before:
        return json.dumps({"success": False, "error": f"未找到任务: {job_id}"})
    _save_jobs(jobs)
    return json.dumps({"success": True})


def cronjob_toggle(job_id: str, enabled: bool) -> str:
    """Enable or disable a cron job."""
    jobs = _load_jobs()
    for job in jobs:
        if job.get("id") == job_id:
            job["enabled"] = enabled
            if enabled and not job.get("next_run_at"):
                job["next_run_at"] = _next_run(job.get("schedule", ""))
            _save_jobs(jobs)
            return json.dumps({"success": True, "enabled": enabled})
    return json.dumps({"success": False, "error": f"未找到任务: {job_id}"})


def cronjob_update(job_id: str, name: str, schedule: str, prompt: str) -> str:
    """Update a cron job's name, schedule, and/or prompt."""
    name = (name or "").strip()
    schedule = (schedule or "").strip()
    prompt = (prompt or "").strip()

    if not name:
        return json.dumps({"success": False, "error": "任务名称不能为空"})

    jobs = _load_jobs()
    for job in jobs:
        if job.get("id") == job_id:
            job["name"] = name
            if schedule:
                # Validate new schedule
                next_nr = _next_run(schedule)
                if next_nr is None:
                    return json.dumps({
                        "success": False,
                        "error": f"无法解析调度表达式: '{schedule}'",
                    })
                job["schedule"] = schedule
                job["next_run_at"] = next_nr
            if prompt:
                job["prompt"] = prompt
            _save_jobs(jobs)
            return json.dumps({
                "success": True,
                "id": job_id,
                "name": name,
                "next_run_at": job.get("next_run_at"),
            }, ensure_ascii=False)
    return json.dumps({"success": False, "error": f"未找到任务: {job_id}"})


def _execute_job_prompt(name: str, prompt: str,
                        session_id: str | None = None,
                        session_title: str | None = None) -> str | None:
    """Run the job's prompt through the AI agent and save as a session.

    If *session_id* is provided, updates that existing session instead of creating
    a new one (used for manual "run now" where the session was pre-created).

    Returns the session_id (existing or new) if successful, None on failure.
    """
    try:
        from agent import config_manager
        from agent.agent import AIAgent
        from agent.core.message_builder import build_system_prompt
        from agent import session_manager, skill_manager, fact_memory, memory_manager

        cfg = config_manager.load()
        api_key = cfg.llm_api_key
        base_url = cfg.llm_base_url
        model = cfg.llm_model
        if not api_key:
            logger.warning("Cron job '%s': no LLM API key configured, skipping execution", name)
            return None

        # Use existing session or create new one
        now = datetime.now(timezone.utc)
        if not session_id:
            time_str = now.strftime("%Y-%m-%d %H:%M")
            session_title = session_title or f"{name} - {time_str}"
            session_id = session_manager.create_session()

        # Build agent with compaction disabled (one-shot execution)
        agent = AIAgent(
            api_key=api_key,
            base_url=base_url,
            model=model,
            max_iterations=15,
            max_tokens=4096,
            system_prompt=(
                "你是 ZLink Agent，一个多 ERP 数据分析助手。\n\n"
                "## 执行守则\n"
                "1. 优先使用技能（Skills）中定义的指令和工具来完成任务\n"
                "2. 其次使用内置工具（如 execute_code、vision_analyze、终端等）\n"
                "3. 最后才使用通用 web_search / web_extract\n"
                "4. 每个步骤都要输出思考过程，最终给出清晰结论\n"
            ),
        )

        memory_store = fact_memory.init_store()
        memory_context = memory_manager.get_context()
        skill_idx = skill_manager.get_active_instructions()

        # Inject ALL active skills' full content (not n-gram filtered)
        # so the AI sees every available skill's instructions
        _all_active = skill_manager.get_active_skills()
        _skill_bodies: list[str] = []
        for _sname in _all_active:
            _body = skill_manager.get_skill_content(_sname)
            if _body:
                if _body.startswith("---"):
                    _parts = _body.split("---", 2)
                    _body = _parts[2].strip() if len(_parts) >= 3 else _body.strip()
                _skill_bodies.append(f"## {_sname}\n\n{_body}")
        skill_detail = (
            "\n\n## 已启用的技能\n\n以下是你可用的技能，请优先使用它们而不是通用搜索工具：\n\n"
            + "\n\n".join(_skill_bodies)
        ) if _skill_bodies else ""

        system_with_memory = build_system_prompt(
            base=agent.system_prompt,
            memory_store=memory_store,
            memory_context=memory_context,
            skill_index=skill_idx,
            skill_detail=skill_detail,
        )

        result = agent.run_conversation(
            user_message=prompt,
            system_message=system_with_memory,
        )

        # Build message list for saving
        messages: list[dict] = [
            {"role": "user", "content": prompt},
        ]
        for msg in result.get("messages", []):
            role = msg.get("role", "")
            if role in ("assistant", "tool"):
                messages.append(msg)

        final = result.get("final_response", "")
        if final and not any(
            m.get("role") == "assistant" and m.get("content") == final for m in messages
        ):
            messages.append({"role": "assistant", "content": final})

        session_manager.save_session(session_id, messages, title=session_title or name)
        logger.info("Cron job '%s' session saved: %s (%s)", name, session_id, session_title or name)
        return session_id

    except Exception as e:
        logger.exception("Cron job '%s' execution failed: %s", name, e)
        return None


def cronjob_run(job_id: str) -> str:
    """Immediately trigger a cron job — creates session, returns for real-time streaming."""
    from agent import session_manager

    jobs = _load_jobs()
    for job in jobs:
        if job.get("id") == job_id:
            now = datetime.now(timezone.utc).isoformat()
            name = job.get("name", "")
            prompt = job.get("prompt", "")

            # Create session with user message so the chat page can find it
            time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
            session_title = f"{name} - {time_str}"
            session_id = session_manager.create_session()
            session_manager.save_session(session_id, [
                {"role": "user", "content": prompt},
            ], title=session_title)

            # Update job record
            job["last_run_at"] = now
            job["last_status"] = "pending"
            job["last_session_id"] = session_id
            schedule = job.get("schedule", "")
            if schedule.startswith("every") or schedule.startswith("daily"):
                next_nr = _next_run(schedule)
                job["next_run_at"] = next_nr or (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
            else:
                job["enabled"] = False
                job["next_run_at"] = None
            _save_jobs(jobs)

            logger.info("Cron job '%s' session created: %s, prompting: %s", name, session_id, prompt[:60])

            return json.dumps({
                "success": True,
                "session_id": session_id,
                "prompt": prompt,
            }, ensure_ascii=False)
    return json.dumps({"success": False, "error": f"未找到任务: {job_id}"})


# ── Schemas & registration ──────────────────────────────────────────────

CRONJOB_LIST_SCHEMA = {
    "name": "cronjob_list",
    "description": "列出所有定时任务及其状态。",
    "parameters": {"type": "object", "properties": {}},
}

CRONJOB_CREATE_SCHEMA = {
    "name": "cronjob_create",
    "description": "创建新的定时任务。支持'every N minutes/hours/days'、'every day at HH:MM'、ISO时间戳。",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "任务名称"},
            "schedule": {"type": "string", "description": "调度表达式，如'every 30 minutes'、'every day at 09:00'、'2026-12-31T23:59:00+00:00'"},
            "prompt": {"type": "string", "description": "任务触发时要发送给 AI 的提示词"},
        },
        "required": ["name", "schedule", "prompt"],
    },
}

CRONJOB_DELETE_SCHEMA = {
    "name": "cronjob_delete",
    "description": "删除一个定时任务。",
    "parameters": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "description": "任务 ID"},
        },
        "required": ["job_id"],
    },
}

CRONJOB_UPDATE_SCHEMA = {
    "name": "cronjob_update",
    "description": "修改定时任务的名称、调度表达式和/或提示词。不传的字段保持不变。",
    "parameters": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "description": "任务 ID"},
            "name": {"type": "string", "description": "新名称"},
            "schedule": {"type": "string", "description": "新调度表达式（可选）"},
            "prompt": {"type": "string", "description": "新提示词（可选）"},
        },
        "required": ["job_id", "name"],
    },
}

CRONJOB_RUN_SCHEMA = {
    "name": "cronjob_run",
    "description": "立即触发一个定时任务（手动执行）。",
    "parameters": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "description": "任务 ID"},
        },
        "required": ["job_id"],
    },
}

CRONJOB_TOGGLE_SCHEMA = {
    "name": "cronjob_toggle",
    "description": "启用或停用一个定时任务。",
    "parameters": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string", "description": "任务 ID"},
            "enabled": {"type": "boolean", "description": "true=启用, false=停用"},
        },
        "required": ["job_id", "enabled"],
    },
}

registry.register(
    name="cronjob_list",
    toolset="cron",
    schema=CRONJOB_LIST_SCHEMA,
    handler=lambda args, **kw: cronjob_list(),
    description="列出所有定时任务",
    emoji="📋",
)

registry.register(
    name="cronjob_create",
    toolset="cron",
    schema=CRONJOB_CREATE_SCHEMA,
    handler=lambda args, **kw: cronjob_create(
        name=args.get("name", ""),
        schedule=args.get("schedule", ""),
        prompt=args.get("prompt", ""),
    ),
    description="创建新定时任务",
    emoji="➕",
    risk_level="medium",
)

registry.register(
    name="cronjob_delete",
    toolset="cron",
    schema=CRONJOB_DELETE_SCHEMA,
    handler=lambda args, **kw: cronjob_delete(
        job_id=args.get("job_id", ""),
    ),
    description="删除定时任务",
    emoji="🗑️",
    risk_level="medium",
)

registry.register(
    name="cronjob_run",
    toolset="cron",
    schema=CRONJOB_RUN_SCHEMA,
    handler=lambda args, **kw: cronjob_run(
        job_id=args.get("job_id", ""),
    ),
    description="立即执行定时任务",
    emoji="▶️",
    risk_level="medium",
)

registry.register(
    name="cronjob_update",
    toolset="cron",
    schema=CRONJOB_UPDATE_SCHEMA,
    handler=lambda args, **kw: cronjob_update(
        job_id=args.get("job_id", ""),
        name=args.get("name", ""),
        schedule=args.get("schedule", ""),
        prompt=args.get("prompt", ""),
    ),
    description="修改定时任务",
    emoji="✏️",
    risk_level="medium",
)

registry.register(
    name="cronjob_toggle",
    toolset="cron",
    schema=CRONJOB_TOGGLE_SCHEMA,
    handler=lambda args, **kw: cronjob_toggle(
        job_id=args.get("job_id", ""),
        enabled=args.get("enabled", True),
    ),
    description="启用/停用定时任务",
    emoji="⏯️",
    risk_level="medium",
)
