"""当前会话上下文 —— 把 session_id 送进工具层，不污染工具签名。

设置点在 :meth:`agent.core.agent_adapter.AIAgent.run_conversation_async`。
工具执行走 ``asyncio.to_thread(registry.dispatch, ...)``，而 ``to_thread``
会 ``copy_context()``，因此 handler / hook 线程内能读到本值；
``FileMutationQueue.enqueue`` 在调用线程内带锁执行，同样可见。

未设置（单测、直接调用工具、未来 CLI）时一切返回 ``None``，调用方必须
回退到改动前的行为（进程 cwd），这是本模块最重要的兼容性约定。
"""

from __future__ import annotations

import contextvars
from pathlib import Path

current_session_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "zlink_current_session_id", default=None
)


def set_current_session(session_id: str | None) -> None:
    """Normalize empty strings to None so downstream checks stay simple."""
    current_session_id.set(session_id or None)


def get_current_session() -> str | None:
    return current_session_id.get()


def current_artifacts_dir() -> Path | None:
    """本次会话的产物目录（不创建）。无会话上下文时返回 None。"""
    sid = current_session_id.get()
    if not sid:
        return None
    from agent import session_manager

    return session_manager.artifacts_dir(sid)


def ensure_current_artifacts_dir() -> Path | None:
    """本次会话的产物目录，不存在则创建。无会话上下文时返回 None。"""
    sid = current_session_id.get()
    if not sid:
        return None
    from agent import session_manager

    return session_manager.ensure_artifacts_dir(sid)


__all__ = [
    "current_session_id",
    "set_current_session",
    "get_current_session",
    "current_artifacts_dir",
    "ensure_current_artifacts_dir",
]
