"""Chat WebSocket endpoint — streams agent execution to the React frontend.

Bridges the synchronous AIAgent loop into FastAPI's asyncio world:
- agent.run_conversation() runs in a ThreadPoolExecutor via run_in_executor
- stream_callback pushes tokens into an asyncio.Queue
- The WebSocket handler pulls from the queue and sends typed JSON messages
- A threading.Event is used for the stop signal (client → agent)
"""

import asyncio
import json
import logging
import os
import threading

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agent import fact_memory, memory_manager, session_manager, skill_manager
from agent.agent import AIAgent
from agent.context_compactor import CompactionSettings
from agent.core.agent import ApprovalRequest
from agent.core.message_builder import build_system_prompt
from agent.slash_commands import execute, parse_command
from agent.tools.registry import discover_tools
from agent.utils import DATA_DIR

logger = logging.getLogger(__name__)

router = APIRouter()

# Ensure tools are discovered at import time
discover_tools()

# Per-session token usage tracking (for /cost command)
_session_usage: dict[str, dict] = {}

# Pending approval requests — keyed by session_id, set by agent thread, resolved by WebSocket coroutine
_pending_approvals: dict[str, ApprovalRequest] = {}
_pending_lock = threading.Lock()


def _set_pending_approval(session_id: str, req: ApprovalRequest | None) -> None:
    with _pending_lock:
        if req is None:
            _pending_approvals.pop(session_id, None)
        else:
            _pending_approvals[session_id] = req


def _resolve_pending_approval(session_id: str, approved: bool) -> bool:
    """Resolve the pending approval for a session. Returns True if one was resolved."""
    with _pending_lock:
        req = _pending_approvals.pop(session_id, None)
    if req is None:
        return False
    req.result = "approved" if approved else "denied"
    req.event.set()
    return True


def _generate_summary(messages: list[dict], api_key: str, base_url: str, model: str) -> str | None:
    """Generate a Chinese conversation summary via LLM."""
    sample = []
    for m in messages:
        role = m.get("role", "")
        if role in ("user", "assistant"):
            content = m.get("content", "")
            if isinstance(content, str) and content:
                sample.append({"role": role, "content": content[:500]})
    sample = sample[-20:]

    if not sample or not api_key:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url.rstrip("/"), timeout=15.0)
        resp = client.chat.completions.create(
            model=model,
            messages=[  # type: ignore[arg-type]
                {
                    "role": "system",
                    "content": "生成一段中文对话摘要，概括用户的核心需求和助手提供的关键信息。控制在100字以内。",
                },
            ]
            + sample,
            max_tokens=150,
            temperature=0.3,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        return None


@router.websocket("/ws/chat/{session_id}")
async def ws_chat(websocket: WebSocket, session_id: str):
    await websocket.accept()

    # Load config
    from agent import config_manager

    cfg = config_manager.load()
    api_key = cfg.llm_api_key
    base_url = cfg.llm_base_url
    model = cfg.llm_model
    max_iterations = cfg.max_iterations
    compaction_settings = CompactionSettings(
        enabled=cfg.compaction_enabled,
        max_context_tokens=cfg.max_context_tokens,
        reserve_tokens=cfg.reserve_tokens,
        keep_recent_tokens=cfg.keep_recent_tokens,
    )

    if not api_key:
        await websocket.send_json({"type": "error", "message": "请先在设置中配置 LLM API Key"})
        await websocket.close()
        return

    # Handle _new session creation
    if session_id == "_new":
        sid = session_manager.create_session()
        session_id = sid

    # Set YonSuite env
    os.environ["YONSUITE_APP_KEY"] = cfg.ys_app_key or ""
    os.environ["YONSUITE_APP_SECRET"] = cfg.ys_app_secret or ""
    os.environ["YONSUITE_TENANT_ID"] = cfg.ys_tenant_id or ""
    os.environ["YONSUITE_GATEWAY_URL"] = cfg.ys_gateway_url or "https://c2.yonyoucloud.com/iuap-api-gateway"
    os.environ["YONSUITE_CACHE_DIR"] = str(DATA_DIR / "yonsuite_cache")

    # Load existing session messages for history context
    existing_msgs = session_manager.load_session(session_id) or []
    history = []
    for m in existing_msgs:
        role = m.get("role", "")
        content = m.get("content", "")
        if role == "tool":
            continue
        if role == "user" and content:
            history.append({"role": "user", "content": content})
        elif role == "assistant" and isinstance(content, str) and content:
            entry = {"role": "assistant", "content": content}
            if "reasoning_content" in m:
                entry["reasoning_content"] = m["reasoning_content"]
            history.append(entry)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "approval_response":
                payload = data.get("payload", {})
                approved = payload.get("approved", False)
                _resolve_pending_approval(session_id, approved)
                continue

            if msg_type == "send_message":
                content = data.get("content", "")
                if not content:
                    continue

                # --- slash command interception ---
                parsed = parse_command(content)
                if parsed:
                    cmd_name, cmd_args = parsed
                    ctx = {
                        "config": cfg,
                        "session_id": session_id,
                        "token_usage": _session_usage.get(session_id),
                    }
                    result = execute(cmd_name, cmd_args, ctx)
                    if result is None:
                        await websocket.send_json(
                            {
                                "type": "done",
                                "final_response": f"未知命令: /{cmd_name}\n\n输入 **/help** 查看所有可用命令。",
                                "messages": [],
                                "api_calls": 0,
                                "token_usage": None,
                                "completed": True,
                                "error": None,
                                "session_id": session_id,
                                "session_title": "",
                            }
                        )
                    elif result == "__YS_CLEAR_SESSION__":
                        # Start a new session
                        sid = session_manager.create_session()
                        old_id = session_id
                        session_id = sid
                        history = []
                        existing_msgs = []
                        _session_usage.pop(old_id, None)
                        await websocket.send_json(
                            {
                                "type": "done",
                                "final_response": "会话已清空，开始新对话。",
                                "messages": [],
                                "api_calls": 0,
                                "token_usage": None,
                                "completed": True,
                                "error": None,
                                "session_id": session_id,
                                "session_title": "",
                            }
                        )
                    else:
                        await websocket.send_json(
                            {
                                "type": "done",
                                "final_response": result,
                                "messages": [],
                                "api_calls": 0,
                                "token_usage": None,
                                "completed": True,
                                "error": None,
                                "session_id": session_id,
                                "session_title": "",
                            }
                        )
                    continue
                # --- end slash command ---

                await _run_agent(
                    websocket,
                    session_id,
                    content,
                    history,
                    api_key,
                    base_url,
                    model,
                    max_iterations,
                    existing_msgs,
                    compaction_settings,
                )
                # After agent finishes, update history with new messages
                updated = session_manager.load_session(session_id) or []
                history = []
                for m in updated:
                    role = m.get("role", "")
                    c = m.get("content", "")
                    if role == "tool":
                        continue
                    if role == "user" and c:
                        history.append({"role": "user", "content": c})
                    elif role == "assistant" and isinstance(c, str) and c:
                        entry = {"role": "assistant", "content": c}
                        if "reasoning_content" in m:
                            entry["reasoning_content"] = m["reasoning_content"]
                        history.append(entry)
                existing_msgs = updated

            elif msg_type == "stop":
                # Stop handled inside _run_agent via threading.Event
                pass

    except WebSocketDisconnect:
        _resolve_pending_approval(session_id, False)
        logger.info("WebSocket disconnected: %s", session_id)
    except Exception:
        _resolve_pending_approval(session_id, False)
        logger.exception("WebSocket error for session %s", session_id)


async def _run_agent(
    websocket: WebSocket,
    session_id: str,
    content: str,
    history: list[dict],
    api_key: str,
    base_url: str,
    model: str,
    max_iterations: int,
    existing_msgs: list[dict],
    compaction_settings: CompactionSettings | None = None,
):
    """Run the agent in a thread pool and stream results via WebSocket."""

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    stop_event = threading.Event()

    # Track stop from client
    stop_received = False

    def stream_callback(token: str):
        loop.call_soon_threadsafe(queue.put_nowait, {"type": "token", "content": token})

    def reasoning_callback(token: str):
        loop.call_soon_threadsafe(queue.put_nowait, {"type": "reasoning_token", "content": token})

    def progress_callback(msg: str):
        loop.call_soon_threadsafe(queue.put_nowait, {"type": "progress", "message": msg})

    # Approval callback — called from agent thread when ApprovalBlockedError is caught
    def _on_approval_request(req: ApprovalRequest) -> None:
        """Called by agent thread when a high-risk tool needs approval."""
        _set_pending_approval(session_id, req)
        # Push approval request to the queue so the WebSocket coroutine sends it
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {
                "type": "approval_request",
                "payload": {
                    "tool_name": req.tool_name,
                    "reason": req.reason,
                },
            },
        )

    def run_sync():
        try:
            agent = AIAgent(
                api_key=api_key,
                base_url=base_url,
                model=model,
                max_iterations=max_iterations,
                progress_callback=progress_callback,
                compaction_settings=compaction_settings,
                approval_callback=_on_approval_request,
            )

            memory_store = fact_memory.init_store()
            memory_context = memory_manager.get_context()
            skill_idx = skill_manager.get_active_instructions()
            skill_detail = skill_manager.get_instructions_for_query(content)

            system_with_memory = build_system_prompt(
                base=agent.system_prompt,
                memory_store=memory_store,
                memory_context=memory_context,
                skill_index=skill_idx,
                skill_detail=skill_detail,
            )

            result = agent.run_conversation(
                user_message=content,
                conversation_history=history,
                system_message=system_with_memory,
                stream_callback=stream_callback,
                reasoning_callback=reasoning_callback,
                stop_event=stop_event,
            )

            # Append new messages to existing + save
            all_msgs = existing_msgs.copy()
            all_msgs.append({"role": "user", "content": content})
            for msg in result.get("messages", []):
                role = msg.get("role", "")
                if role in ("assistant", "tool"):
                    all_msgs.append(msg)
            if result.get("final_response") and not any(
                m.get("role") == "assistant" and m.get("content") == result["final_response"] for m in all_msgs
            ):
                all_msgs.append({"role": "assistant", "content": result["final_response"]})

            title = session_manager.auto_title(all_msgs)
            session_manager.save_session(session_id, all_msgs, title)

            # Generate summary if enough assistant messages
            asst_count = len(
                [
                    m
                    for m in all_msgs
                    if m.get("role") == "assistant" and isinstance(m.get("content"), str) and m["content"]
                ]
            )
            if asst_count >= 2:
                summary = _generate_summary(all_msgs, api_key, base_url, model)
                memory_manager.store_conversation_summary(session_id, title, all_msgs, summary=summary)

            loop.call_soon_threadsafe(
                queue.put_nowait,
                {
                    "type": "done",
                    "final_response": result.get("final_response", ""),
                    "messages": result.get("messages", []),
                    "api_calls": result.get("api_calls", 0),
                    "token_usage": result.get("token_usage"),
                    "completed": result.get("completed", False),
                    "error": result.get("error"),
                    "session_id": session_id,
                    "session_title": title,
                },
            )
        except Exception as e:
            logger.exception("Agent execution failed")
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {
                    "type": "error",
                    "message": str(e),
                    "session_id": session_id,
                },
            )

    # Start agent in thread pool
    future = loop.run_in_executor(None, run_sync)

    # Listen for stop messages from client with a timeout-based poll
    async def listen_for_stop():
        nonlocal stop_received
        try:
            while not stop_received and not stop_event.is_set():
                try:
                    raw = await asyncio.wait_for(websocket.receive_text(), timeout=0.2)
                    data = json.loads(raw)
                    if data.get("type") == "stop":
                        stop_received = True
                        stop_event.set()
                    elif data.get("type") == "approval_response":
                        payload = data.get("payload", {})
                        approved = payload.get("approved", False)
                        _resolve_pending_approval(session_id, approved)
                except TimeoutError:
                    pass
                except Exception:
                    _resolve_pending_approval(session_id, False)
                    break
        except Exception:
            pass

    stop_task = asyncio.create_task(listen_for_stop())

    # Drain queue → WebSocket
    done_received = False
    while not done_received:
        msg = await queue.get()
        try:
            await websocket.send_json(msg)
        except RuntimeError:
            # WebSocket already closed — stop draining
            break
        if msg["type"] in ("done", "error"):
            done_received = True

    stop_task.cancel()
    try:
        await stop_task
    except asyncio.CancelledError:
        pass
