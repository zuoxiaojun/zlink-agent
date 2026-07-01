"""File mutation queue — sequential execution for write/patch operations.

Pi-inspired: when multiple tool calls target the same file, processing
them sequentially (not concurrently) prevents race conditions.

Usage
-----
The queue is used transparently via :func:`enqueue_write` /
:func:`enqueue_patch`.  Callers who need synchronous (bypass) access
use :func:`flush_queue` first.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Mutation:
    path: str
    kind: str  # "write" or "patch"
    args: dict[str, Any]
    result: str | None = None
    error: str | None = None


class FileMutationQueue:
    """Thread-safe sequential queue for file mutations.

    All write/patch operations go through this queue so that
    concurrent tool calls touching the same file don't race.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queue: list[Mutation] = []
        self._executor: Callable[[str, dict], str] | None = None

    def set_executor(self, executor: Callable[[str, dict], str]) -> None:
        """Set the function that actually performs mutations.

        ``executor(kind, args)`` returns a JSON result string, same
        shape as a tool handler.
        """
        self._executor = executor

    def enqueue(self, kind: str, args: dict) -> str:
        """Add a mutation to the queue and execute all pending mutations.

        Returns the result of the *entire queue* (all mutations up to
        and including this one are flushed).  This ensures sequential
        consistency — callers that read a file after writing see the
        latest state.
        """
        mutation = Mutation(path=args.get("path", ""), kind=kind, args=args)
        return self._flush(mutation)

    def _flush(self, mutation: Mutation) -> str:
        """Execute *mutation* and all earlier queued ones.  Thread-safe."""
        executor = self._executor
        if executor is None:
            return '{"success": false, "error": "FileMutationQueue has no executor set"}'

        with self._lock:
            self._queue.append(mutation)
            results: list[str] = []
            errors: list[str] = []
            while self._queue:
                m = self._queue[0]
                if m.result is not None:
                    results.append(m.result)
                    self._queue.pop(0)
                    continue
                try:
                    result = executor(m.kind, m.args)
                    m.result = result
                    results.append(result)
                except Exception as e:
                    logger.exception("Mutation %s(%s) failed", m.kind, m.path)
                    err = tool_error(str(e))
                    m.result = err
                    errors.append(str(e))
                self._queue.pop(0)
            # Return the last successful result, or the error if all failed
            if results:
                return results[-1]
            return tool_error("; ".join(errors) if errors else "Unknown queue error")

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._queue)

    def clear(self) -> None:
        with self._lock:
            self._queue.clear()


def tool_error(message: str) -> str:
    import json

    return json.dumps({"success": False, "error": message})


def tool_result(**kwargs: Any) -> str:
    import json

    return json.dumps({"success": True, "data": kwargs.get("data", ""), **kwargs})


# Module-level singleton — the file tool module shares this.
file_mutation_queue = FileMutationQueue()
