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
from agent.core.kernel_types import AgentEvent
from agent.core.message_builder import build_system_prompt
from agent.slash_commands import execute, parse_command
from agent.utils import DATA_DIR

logger = logging.getLogger(__name__)

router = APIRouter()

# 工具发现由 AIAgent._ensure_discovered() 懒加载，无需在模块顶层调用
# discover_tools() —— 保持在后端启动关键路径之外。

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
                _skill_override: dict[str, str] = {}
                parsed = parse_command(content)
                if parsed:
                    cmd_name, cmd_args = parsed
                    ctx = {
                        "config": cfg,
                        "session_id": session_id,
                        "token_usage": _session_usage.get(session_id),
                    }
                    result = execute(cmd_name, cmd_args, ctx)

                    # result is None → unknown command, check skill match
                    if result is None:
                        _skill_body = skill_manager.get_skill_content(cmd_name)
                        if _skill_body is not None:
                            _skill_override["detail"] = _skill_body
                            content = cmd_args or f"请帮我使用 {cmd_name} 技能"
                        else:
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
                            continue

                    # result is a sentinel → clear session
                    elif result == "__YS_CLEAR_SESSION__":
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
                        continue

                    # result is a string → normal command output
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

                    # Skill match: fall through to _run_agent (no continue)
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
                    skill_detail=_skill_override.get("detail"),
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
    skill_detail: str | None = None,
):
    """Direct-await path (spec §4.6)."""
    await _run_agent_new(
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
        skill_detail,
    )


async def _run_agent_new(
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
    skill_detail: str | None = None,
):
    """Direct-await path (spec §4.6): an AgentEvent listener converts
    events into the existing flat WS message types, in order."""

    async def _send(msg: dict) -> None:
        try:
            await websocket.send_json(msg)
        except Exception:  # noqa: BLE001 — WS closed (e.g. RuntimeError, ClosedResourceError); best-effort send
            pass

    send_tasks: list[asyncio.Task] = []
    stop_received = False

    def _on_approval_request(req: ApprovalRequest) -> None:
        _set_pending_approval(session_id, req)
        send_tasks.append(
            asyncio.create_task(
                _send(
                    {
                        "type": "approval_request",
                        "payload": {"tool_name": req.tool_name, "reason": req.reason},
                    }
                )
            )
        )

    agent = AIAgent(
        api_key=api_key,
        base_url=base_url,
        model=model,
        max_iterations=max_iterations,
        compaction_settings=compaction_settings,
        approval_callback=_on_approval_request,
    )

    memory_store = fact_memory.init_store()
    memory_context = memory_manager.get_context()
    skill_idx = skill_manager.get_active_instructions()
    resolved_skill = skill_detail if skill_detail is not None else skill_manager.get_instructions_for_query(content)
    system_with_memory = build_system_prompt(
        base=agent.system_prompt,
        memory_store=memory_store,
        memory_context=memory_context,
        skill_index=skill_idx,
        skill_detail=resolved_skill,
    )

    turn_no = 0
    tool_no = 0

    def _on_event(event: AgentEvent) -> None:
        nonlocal turn_no, tool_no
        t = event.type
        if t == "message_start" and event.message.get("role") == "assistant":
            turn_no += 1
            send_tasks.append(
                asyncio.create_task(
                    _send({"type": "progress", "message": f"🤔 思考中...（第 {turn_no}/{max_iterations} 轮）"})
                )
            )
        elif t == "message_update":
            if event.delta:
                send_tasks.append(asyncio.create_task(_send({"type": "token", "content": event.delta})))
            if event.reasoning_delta:
                send_tasks.append(
                    asyncio.create_task(_send({"type": "reasoning_token", "content": event.reasoning_delta}))
                )
        elif t == "tool_execution_start":
            try:
                args_str = json.dumps(event.args, ensure_ascii=False)[:200]
            except (TypeError, ValueError):
                args_str = str(event.args)[:200]
            send_tasks.append(
                asyncio.create_task(_send({"type": "tool_call", "name": event.tool_name, "arguments": args_str}))
            )
            send_tasks.append(
                asyncio.create_task(
                    _send({"type": "progress", "message": f"🔧 执行工具: {event.tool_name} | {args_str}"})
                )
            )
        elif t == "tool_execution_end":
            payload: dict = {"type": "tool_result", "name": event.tool_name, "result": event.result}
            if event.denied:
                payload["denied"] = True
            send_tasks.append(asyncio.create_task(_send(payload)))
        elif t == "turn_end" and event.tool_results:
            tool_no += 1
            send_tasks.append(
                asyncio.create_task(_send({"type": "progress", "message": f"✅ 工具执行完成 (第 {tool_no} 轮)"}))
            )

    agent.agent.subscribe(_on_event)

    async def _listen_inbound():
        nonlocal stop_received
        while not stop_received:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=0.2)
            except TimeoutError:
                continue
            except Exception:
                _resolve_pending_approval(session_id, False)
                return
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            mtype = data.get("type", "")
            if mtype == "stop":
                stop_received = True
                agent.cancel()
            elif mtype == "approval_response":
                payload = data.get("payload", {})
                _resolve_pending_approval(session_id, payload.get("approved", False))
            elif mtype == "steering":
                payload = data.get("payload", {})
                content = payload.get("content", "")
                if content:
                    agent.steer({"role": "user", "content": content})

    listen_task = asyncio.create_task(_listen_inbound())
    error: str | None = None
    result: dict | None = None
    try:
        # stream/reasoning 回调必须非 None —— adapter 以此决定是否开启
        # LLM 流式调用并把 MessageUpdate（token / reasoning_delta）事件
        # 推到 Agent 事件流；WS 转发由上方 _on_event 订阅完成，
        # 所以这里的回调本体无需做任何事。
        result = await agent.run_conversation_async(
            user_message=content,
            conversation_history=history,
            system_message=system_with_memory,
            session_id=session_id,
            stream_callback=lambda _chunk: None,
            reasoning_callback=lambda _chunk: None,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("Agent execution failed")
        error = str(e)
    finally:
        stop_received = True
        listen_task.cancel()
        try:
            await listen_task
        except asyncio.CancelledError:
            pass
        if send_tasks:
            await asyncio.gather(*send_tasks, return_exceptions=True)

    # ── session persistence + done (fields identical to the old path) ──
    all_msgs = existing_msgs.copy()
    all_msgs.append({"role": "user", "content": content})
    new_msgs = (result or {}).get("messages", [])[len(history) + 1 :]  # 跳过 history + 当前 user
    for msg in new_msgs:
        role = msg.get("role", "")
        if role in ("assistant", "tool"):
            all_msgs.append(msg)
    if (
        result
        and result.get("final_response")
        and not any(m.get("role") == "assistant" and m.get("content") == result["final_response"] for m in all_msgs)
    ):
        all_msgs.append({"role": "assistant", "content": result["final_response"]})

    title = session_manager.auto_title(all_msgs)
    session_manager.save_session(session_id, all_msgs, title)

    if error is not None:
        await _send({"type": "error", "message": error, "session_id": session_id})
    else:
        await _send(
            {
                "type": "done",
                "final_response": (result or {}).get("final_response", ""),
                "api_calls": (result or {}).get("api_calls", 0),
                "token_usage": (result or {}).get("token_usage"),
                "completed": (result or {}).get("completed", False),
                "error": (result or {}).get("error"),
                "session_id": session_id,
                "session_title": title,
            }
        )

    asst_count = len(
        [m for m in all_msgs if m.get("role") == "assistant" and isinstance(m.get("content"), str) and m["content"]]
    )
    if asst_count >= 2:
        summary = await asyncio.to_thread(_generate_summary, all_msgs, api_key, base_url, model)
        if summary:
            memory_manager.store_conversation_summary(session_id, title, all_msgs, summary=summary)
