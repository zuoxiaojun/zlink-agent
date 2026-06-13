"""Session REST API — thin wrappers around session_manager."""

from fastapi import APIRouter, HTTPException

from agent import session_manager
from backend.schemas.session import SessionCreate, SessionDetail, SessionRename, SessionSummary

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionSummary])
def list_sessions():
    return session_manager.list_sessions()


@router.post("", response_model=SessionSummary)
def create_session(body: SessionCreate = SessionCreate()):
    sid = session_manager.create_session(title=body.title)
    sessions = session_manager.list_sessions()
    for s in sessions:
        if s["id"] == sid:
            return s
    return SessionSummary(id=sid, title=body.title, created_at="", updated_at="", message_count=0)


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(session_id: str):
    messages = session_manager.load_session(session_id)
    if messages is None:
        raise HTTPException(status_code=404, detail="Session not found")
    sessions = session_manager.list_sessions()
    title = ""
    for s in sessions:
        if s["id"] == session_id:
            title = s["title"]
            break
    return SessionDetail(id=session_id, title=title, messages=messages)


@router.put("/{session_id}", response_model=SessionSummary)
def rename_session(session_id: str, body: SessionRename):
    sessions = session_manager.list_sessions()
    for s in sessions:
        if s["id"] == session_id:
            session_manager.save_session(
                session_id,
                session_manager.load_session(session_id) or [],
                body.title,
            )
            s["title"] = body.title
            return s
    raise HTTPException(status_code=404, detail="Session not found")


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: str):
    sessions = session_manager.list_sessions()
    if not any(s["id"] == session_id for s in sessions):
        raise HTTPException(status_code=404, detail="Session not found")
    session_manager.delete_session(session_id)
