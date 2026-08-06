"""Stateful Agent wrapper — the Pi-style ``agent.ts`` counterpart.

Pi-style kernel redesign (spec 2026-08-06-pi-style-kernel-design).
This module is the NEW kernel entry point: a thin stateful wrapper
(``subscribe`` / ``steer`` / ``follow_up`` / ``cancel`` / ``wait_idle``)
around the stateless loop in :mod:`agent.core.loop`.  The legacy
``AIAgent`` compatibility layer lives in :mod:`agent.core.agent_adapter`
and is re-exported at the bottom of this module so
``from agent.core.agent import AIAgent`` keeps working (frozen contract
C1).
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from agent.core.kernel_types import (
    AgentContext,
    AgentEvent,
    AgentLoopConfig,
    CancelToken,
    ToolExecutionEnd,
    ToolExecutionStart,
)
from agent.core.loop import run_agent_loop

logger = logging.getLogger(__name__)


@dataclass
class AgentState:
    """Read-only-ish view of the agent's current run state."""

    messages: list[dict] = field(default_factory=list)
    pendingToolCalls: int = 0  # noqa: N815 — Pi-style camelCase (frozen T6 contract)
    running: bool = False


class Agent:
    """Stateful wrapper around :func:`run_agent_loop`.

    Owns the steering/follow-up queues, the cancel token, the listener
    registry and a lightweight :class:`AgentState` view.  One instance
    runs one conversation at a time.
    """

    def __init__(self) -> None:
        self.state = AgentState()
        self._steering: deque[dict] = deque()
        self._follow_ups: deque[dict] = deque()
        self._listeners: list[Callable[[AgentEvent], None]] = []
        self._token = CancelToken()

    # ── listener API ──

    def subscribe(self, listener: Callable[[AgentEvent], None]) -> Callable[[], None]:
        """Register a sync listener.  Idempotent: re-subscribing the same
        listener is a no-op.  Returns an unsubscribe callable."""
        if listener not in self._listeners:
            self._listeners.append(listener)

        def _unsub() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _unsub

    # ── queue API ──

    def steer(self, message: dict) -> None:
        """Inject a steering message; consumed one-at-a-time (oldest
        first) at the next turn boundary."""
        self._steering.append(message)

    def follow_up(self, message: dict) -> None:
        self._follow_ups.append(message)

    def clear_steering_queue(self) -> None:
        self._steering.clear()

    def next_steering_message(self) -> list[dict]:
        """Drain at most ONE steering message (one-at-a-time)."""
        if not self._steering:
            return []
        return [self._steering.popleft()]

    def next_follow_up_messages(self) -> list[dict]:
        """Drain all pending follow-up messages."""
        if not self._follow_ups:
            return []
        out = list(self._follow_ups)
        self._follow_ups.clear()
        return out

    # ── lifecycle API ──

    def cancel(self) -> None:
        self._token.cancel()

    async def wait_idle(self) -> None:
        while self.state.running:
            await asyncio.sleep(0.01)

    async def run_async(
        self,
        prompts: list[dict],
        config: AgentLoopConfig,
        token: CancelToken | None = None,
    ) -> list[dict]:
        """Run one conversation.  Returns the new messages
        (prompts + everything the loop appended)."""
        if token is not None:
            self._token = token
        elif self._token.cancelled:
            self._token = CancelToken()
        context = AgentContext(messages=[], api_calls=0)
        self.state.running = True
        self.state.messages = list(prompts)
        self.state.pendingToolCalls = 0
        try:
            result = await run_agent_loop(prompts, context, config, self._emit, self._token)
            # The frozen loop's AgentContext only carries prompts/steering/tool
            # messages (not assistant replies), so the full transcript is the
            # loop's return value — that is what the state view must expose.
            self.state.messages = list(result)
            return result
        finally:
            self.state.running = False

    async def _emit(self, event: AgentEvent) -> None:
        """Fan out one AgentEvent to listeners + maintain state.

        Listener exceptions propagate (the adapter's mapper swallows
        EventBus subscriber errors internally, so only intentional
        control-flow exceptions escape — e.g. run cancellation).
        """
        if isinstance(event, ToolExecutionStart):
            self.state.pendingToolCalls += 1
        elif isinstance(event, ToolExecutionEnd):
            self.state.pendingToolCalls = max(0, self.state.pendingToolCalls - 1)
        for listener in list(self._listeners):
            listener(event)


# ── legacy-compat re-exports (frozen contract C1) ──────────────────
from agent.core.agent_adapter import (  # noqa: E402, I001
    AIAgent,
    AgentPhase,
    ApprovalRequest,
    Envelope,
    Phase,
    TurnSnapshot,
)

__all__ = [
    "Agent",
    "AgentState",
    "AIAgent",
    "AgentPhase",
    "ApprovalRequest",
    "Envelope",
    "Phase",
    "TurnSnapshot",
]
