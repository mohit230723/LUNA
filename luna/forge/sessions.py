"""Registry of connected coding-agent sessions."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from luna.forge.events import AGENT_CONNECTED, AGENT_SEEN, ForgeEventBus

SEEN_THROTTLE = timedelta(seconds=30)
IDLE_TIMEOUT = timedelta(minutes=5)


class SessionRegistry:
    def __init__(self, bus: ForgeEventBus) -> None:
        self._bus = bus
        self._lock = threading.Lock()
        self._sessions: dict[str, dict[str, Any]] = {}
        self._last_emit: dict[str, datetime] = {}

    def touch(
        self,
        session_id: str,
        client_name: str = "",
        client_version: str = "",
        now: datetime | None = None,
    ) -> None:
        now = now or datetime.now(timezone.utc)
        event: tuple[str, dict[str, Any]] | None = None
        with self._lock:
            s = self._sessions.get(session_id)
            if s is None:
                s = {
                    "session_id": session_id,
                    "client_name": client_name,
                    "client_version": client_version,
                    "first_seen": now,
                    "last_seen": now,
                }
                self._sessions[session_id] = s
                self._last_emit[session_id] = now
                event = (AGENT_CONNECTED, {"session_id": session_id, "client_name": client_name,
                                           "client_version": client_version})
            else:
                if client_name:
                    s["client_name"] = client_name
                if client_version:
                    s["client_version"] = client_version
                if now > s["last_seen"]:
                    s["last_seen"] = now
                if now - self._last_emit[session_id] >= SEEN_THROTTLE:
                    self._last_emit[session_id] = now
                    event = (AGENT_SEEN, {"session_id": session_id, "client_name": s["client_name"]})
        if event:
            self._bus.publish(*event)

    def list(self, now: datetime | None = None) -> list[dict[str, Any]]:
        now = now or datetime.now(timezone.utc)
        with self._lock:
            rows = [
                {
                    "session_id": s["session_id"],
                    "client_name": s["client_name"],
                    "client_version": s["client_version"],
                    "first_seen": s["first_seen"].isoformat(),
                    "last_seen": s["last_seen"].isoformat(),
                    "connected": now - s["last_seen"] < IDLE_TIMEOUT,
                    "_ls": s["last_seen"],
                }
                for s in self._sessions.values()
            ]
        rows.sort(key=lambda r: r["_ls"], reverse=True)
        for r in rows:
            del r["_ls"]
        return rows
