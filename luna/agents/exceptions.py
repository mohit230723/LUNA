"""Exceptions for agent execution and LLM availability."""


class LLMUnavailableError(RuntimeError):
    """Raised in strict_llm mode when LLM synthesis fails and fallback is blocked."""
    pass
