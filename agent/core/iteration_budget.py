"""Iteration budget — extracted unchanged from agent.py.

Kept as a separate file so M3 can replace the simple counter with a
token-budget version without touching the agent loop.
"""
from __future__ import annotations


class IterationBudget:
    """Simple iteration counter for the agent loop."""

    def __init__(self, max_total: int) -> None:
        self.max_total = max_total
        self._used = 0

    def consume(self) -> bool:
        if self._used >= self.max_total:
            return False
        self._used += 1
        return True

    @property
    def used(self) -> int:
        return self._used

    @property
    def remaining(self) -> int:
        return max(0, self.max_total - self._used)
