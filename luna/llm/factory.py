"""Factory for instantiating LLM providers."""

from __future__ import annotations

import os
from typing import Optional

from luna.llm.client import LLMClient, OllamaLLM, MockLLMClient
from luna.llm.openai import OpenAICompatibleLLM
from luna.llm.anthropic import AnthropicLLM
from luna.llm.gemini import GeminiLLM


def get_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    pack: Optional[str] = None,
) -> LLMClient:
    """Return an LLMClient instance based on configuration and environment variables.

    Supported providers: 'ollama', 'openai_compatible' (or 'openai'), 'anthropic', 'gemini', 'mock'.
    """
    raw_prov = provider or os.getenv("LUNA_LLM_PROVIDER", "ollama")
    prov = raw_prov.lower().strip()

    # Model resolution
    resolved_model = model
    if not resolved_model:
        if pack == "build":
            resolved_model = os.getenv("LUNA_MODEL_BUILD")
        elif pack == "investigate":
            resolved_model = os.getenv("LUNA_MODEL_INVESTIGATE")
        if not resolved_model:
            resolved_model = os.getenv("LUNA_LLM_MODEL")

    if prov in ("openai", "openai_compatible"):
        b_url = base_url or os.getenv("LUNA_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        key = api_key or os.getenv("LUNA_LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        m_name = resolved_model or "gpt-4o-mini"
        return OpenAICompatibleLLM(base_url=b_url, api_key=key, model=m_name)

    elif prov == "anthropic":
        key = api_key or os.getenv("ANTHROPIC_API_KEY") or os.getenv("LUNA_LLM_API_KEY")
        b_url = base_url or os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        m_name = resolved_model or "claude-3-5-sonnet-20241022"
        return AnthropicLLM(api_key=key, model=m_name, base_url=b_url)

    elif prov == "gemini":
        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("LUNA_LLM_API_KEY")
        b_url = base_url or "https://generativelanguage.googleapis.com/v1beta"
        m_name = resolved_model or "gemini-1.5-flash"
        return GeminiLLM(api_key=key, model=m_name, base_url=b_url)

    elif prov == "mock":
        return MockLLMClient()

    else:
        # Default: Ollama
        b_url = base_url or os.getenv("LUNA_LLM_BASE_URL") or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        m_name = resolved_model or os.getenv("OLLAMA_MODEL") or "llama3.2"
        return OllamaLLM(base_url=b_url, model=m_name)


# Alias
get_llm_client = get_llm
