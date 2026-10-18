"""Unit tests for the Forge event bus and session registry."""

import threading
import time
from datetime import datetime, timedelta, timezone

from luna.forge.events import AGENT_CONNECTED, RUN_CREATED, ForgeEventBus
from luna.forge.sessions import SessionRegistry

T0 = datetime(2026, 10, 19, 10, 0, 0, tzinfo=timezone.utc)


def test_bus_sequence_and_wait_after():
    bus = ForgeEventBus()
    ev = bus.publish("run_created", {"run_id": "r1"})
    assert ev["seq"] == 1 and ev["type"] == "run_created" and ev["data"] == {"run_id": "r1"}
    datetime.fromisoformat(ev["ts"])
    assert [e["seq"] for e in bus.wait_after(0, 0.01)] == [1]
    assert bus.wait_after(1, 0.01) == []
    assert RUN_CREATED == "run_created" and AGENT_CONNECTED == "agent_connected"


def test_bus_ring_buffer_keeps_500():
    bus = ForgeEventBus()
    for i in range(600):
        bus.publish("x", {"i": i})
    events = bus.wait_after(0, 0.01)
    assert len(events) == 500
    assert events[0]["seq"] == 101 and events[-1]["seq"] == 600


def test_bus_wait_blocks_until_publish_many_waiters():
    bus = ForgeEventBus()
    results = []

    def waiter():
        results.append([e["seq"] for e in bus.wait_after(0, 5)])

    threads = [threading.Thread(target=waiter) for _ in range(5)]
    for t in threads:
        t.start()
    time.sleep(0.1)
    bus.publish("x", {})
    for t in threads:
        t.join(3)
    assert results == [[1]] * 5


def test_sessions_connect_seen_throttle_and_disconnect():
    bus = ForgeEventBus()
    reg = SessionRegistry(bus)
    reg.touch("s1", "claude-code", "2.1", now=T0)
    reg.touch("s1", now=T0 + timedelta(seconds=10))
    reg.touch("s1", now=T0 + timedelta(seconds=40))
    assert [e["type"] for e in bus.wait_after(0, 0.01)] == ["agent_connected", "agent_seen"]
    assert reg.list(now=T0 + timedelta(minutes=6))[0]["connected"] is False
    assert reg.list(now=T0)[0]["client_name"] == "claude-code"


def test_sessions_list_newest_first():
    reg = SessionRegistry(ForgeEventBus())
    reg.touch("a", now=T0)
    reg.touch("b", now=T0 + timedelta(seconds=5))
    assert [s["session_id"] for s in reg.list(now=T0 + timedelta(seconds=6))] == ["b", "a"]
