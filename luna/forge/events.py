"""In-process event bus feeding the Forge Platform page (SSE)."""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

AGENT_CONNECTED = "agent_connected"
AGENT_SEEN = "agent_seen"
RUN_CREATED = "run_created"
TASK_UPDATED = "task_updated"
TASK_STALLED = "task_stalled"
RUN_ASSEMBLED = "run_assembled"
SKILL_IMPORTED = "skill_imported"
HELLO = "hello"  # first SSE frame only; never published on the bus

MAX_EVENTS = 500


class ForgeEventBus:
    """Thread-safe ring buffer of the last 500 events with blocking reads."""

    def __init__(self) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=MAX_EVENTS)
        self._seq = 0
        self._lock = threading.Lock()
        self.condition = threading.Condition(self._lock)

    def publish(self, type: str, data: dict[str, Any]) -> dict[str, Any]:
        with self.condition:
            self._seq += 1
            ev = {
                "seq": self._seq,
                "ts": datetime.now(timezone.utc).isoformat(),
                "type": type,
                "data": data,
            }
            self._events.append(ev)
            self.condition.notify_all()
            return ev

    def current_seq(self) -> int:
        """Sequence number of the newest published event (0 if none)."""
        with self.condition:
            return self._seq

    def wait_after(self, seq: int, timeout: float) -> list[dict[str, Any]]:
        """Return events newer than ``seq``; block up to ``timeout`` if none."""
        deadline = time.monotonic() + max(0.0, timeout)
        with self.condition:
            while True:
                if self._seq > seq:
                    return [e for e in self._events if e["seq"] > seq]
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return []
                self.condition.wait(remaining)
