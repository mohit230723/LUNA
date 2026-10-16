"""Tests for ask_graph backend choice and pluggable AskGraphBackend protocol (F12)."""

import os
import pytest
from unittest.mock import MagicMock
from luna.tools.ask_graph import (
    AskGraphBackend,
    CustomTranslatorBackend,
    GraphRagSdkBackend,
    get_ask_backend,
    ask_graph,
)
from luna.graph.store import GraphStore


def test_custom_translator_backend_implements_protocol() -> None:
    backend = CustomTranslatorBackend()
    assert isinstance(backend, AskGraphBackend)
    cypher = backend.ask("test_graph", "Find customers with shared bank account")
    assert "BankAccount" in cypher
    assert "RETURN" in cypher


def test_backend_selection_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Default is custom
    monkeypatch.delenv("LUNA_ASK_BACKEND", raising=False)
    backend = get_ask_backend()
    assert isinstance(backend, CustomTranslatorBackend)

    # Explicit custom
    monkeypatch.setenv("LUNA_ASK_BACKEND", "custom")
    backend = get_ask_backend()
    assert isinstance(backend, CustomTranslatorBackend)

    # SDK selection
    monkeypatch.setenv("LUNA_ASK_BACKEND", "sdk")
    try:
        sdk_backend = get_ask_backend()
        assert isinstance(sdk_backend, GraphRagSdkBackend)
    except ImportError as e:
        # Expected on Windows without C++ compiler toolchain for hnswlib
        assert "graphrag" in str(e).lower() or "hnswlib" in str(e).lower()

    # Invalid selection
    monkeypatch.setenv("LUNA_ASK_BACKEND", "unsupported_backend")
    with pytest.raises(ValueError, match="Unknown ask_graph backend"):
        get_ask_backend()


def test_unsafe_cypher_from_backend_is_blocked() -> None:
    class MaliciousBackend:
        def ask(self, graph: str, question: str) -> str:
            return "MATCH (c:Customer) DELETE c RETURN c"

    store = MagicMock(spec=GraphStore)
    res = ask_graph(
        store=store,
        graph_name="test_graph",
        question="delete all records",
        backend=MaliciousBackend(),
    )

    assert res == {"error": "unsafe_query"}
    store.read_query.assert_not_called()
    store.query.assert_not_called()
