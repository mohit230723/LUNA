"""Tests for Q2: LLM Provider Layer (Ollama, OpenAI, Anthropic, Mock, Factory)."""

import os
import pytest
from luna.llm.client import MockLLMClient, ToolLoopResult
from luna.llm.openai import OpenAICompatibleLLM, _mask_api_key as mask_openai_key
from luna.llm.anthropic import AnthropicLLM, _mask_api_key as mask_anthropic_key
from luna.llm.factory import get_llm_client


def test_mock_llm_complete_json() -> None:
    """Verify MockLLMClient complete_json returns structured dictionary."""
    mock = MockLLMClient(default_response={"status": "success", "count": 42})
    data = mock.complete_json("give me data")
    assert isinstance(data, dict)
    assert data["status"] == "success"
    assert data["count"] == 42


def test_mock_llm_run_tool_loop() -> None:
    """Verify MockLLMClient run_tool_loop returns valid ToolLoopResult."""
    mock = MockLLMClient(default_response="Task complete")
    res = mock.run_tool_loop("Solve task", tools=[])
    assert isinstance(res, ToolLoopResult)
    assert res.content == "Task complete"
    assert res.iterations >= 1


def test_openai_provider_zero_leak_key() -> None:
    """Verify OpenAICompatibleLLM masks API key in repr, str, and helper."""
    secret = "sk-proj-supersecretkey1234567890abcdef"
    llm = OpenAICompatibleLLM(api_key=secret, model="gpt-4o")

    # API key is never exposed in repr or str
    assert secret not in repr(llm)
    assert secret not in str(llm)
    assert "..." in repr(llm)

    # Mask helper
    masked = mask_openai_key(secret)
    assert masked.startswith("sk-p")
    assert masked.endswith("cdef")
    assert secret not in masked


def test_anthropic_provider_zero_leak_key() -> None:
    """Verify AnthropicLLM masks API key in repr, str, and helper."""
    secret = "sk-ant-api03-superconfidentialkey9876543210"
    llm = AnthropicLLM(api_key=secret, model="claude-3-5-sonnet-20241022")

    assert secret not in repr(llm)
    assert secret not in str(llm)
    assert "..." in repr(llm)

    masked = mask_anthropic_key(secret)
    assert masked.startswith("sk-a")
    assert masked.endswith("3210")
    assert secret not in masked


def test_factory_returns_mock() -> None:
    """Verify get_llm_client returns MockLLMClient when requested."""
    client = get_llm_client(provider="mock")
    assert isinstance(client, MockLLMClient)


def test_factory_returns_openai_with_model() -> None:
    """Verify get_llm_client returns OpenAICompatibleLLM with correct model."""
    client = get_llm_client(provider="openai", model="deepseek-chat")
    assert isinstance(client, OpenAICompatibleLLM)
    assert client.model == "deepseek-chat"


def test_factory_returns_anthropic() -> None:
    """Verify get_llm_client returns AnthropicLLM."""
    client = get_llm_client(provider="anthropic")
    assert isinstance(client, AnthropicLLM)


def test_factory_per_pack_model_overrides(monkeypatch) -> None:
    """Verify per-pack model overrides take precedence."""
    monkeypatch.setenv("LUNA_MODEL_BUILD", "qwen2.5-coder:32b")
    monkeypatch.setenv("LUNA_MODEL_INVESTIGATE", "llama3.3:70b")

    build_client = get_llm_client(provider="ollama", pack="build")
    assert build_client.model == "qwen2.5-coder:32b"

    inv_client = get_llm_client(provider="ollama", pack="investigate")
    assert inv_client.model == "llama3.3:70b"
