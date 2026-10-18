"""LLMClient protocol, Ollama provider, and deterministic MockLLMClient."""

import json
import re
from typing import Any, Optional, Protocol, Union
from luna.config import settings


class LLMClient(Protocol):
    """Protocol defining the interface for LLM completion requests."""

    def complete(
        self,
        prompt: str,
        system: str = "",
        json_schema: Optional[dict[str, Any]] = None,
    ) -> Union[dict[str, Any], str]:
        """Generate a response from the language model."""
        ...


class OllamaLLM:
    """Ollama language model provider using LangChain ChatOllama."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
    ) -> None:
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.OLLAMA_MODEL
        self.temperature = temperature
        self._llm: Any = None

    @property
    def llm(self) -> Any:
        """Lazily initialize ChatOllama instance."""
        if self._llm is None:
            from langchain_ollama import ChatOllama
            self._llm = ChatOllama(
                base_url=self.base_url,
                model=self.model,
                temperature=self.temperature,
            )
        return self._llm

    def complete(
        self,
        prompt: str,
        system: str = "",
        json_schema: Optional[dict[str, Any]] = None,
    ) -> Union[dict[str, Any], str]:
        """Send prompt to Ollama and return text or structured JSON."""
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))

        # Request structured JSON format if schema is specified
        if json_schema is not None:
            bound_llm = self.llm.bind(format="json")
            response = bound_llm.invoke(messages)
            content = response.content if hasattr(response, "content") else str(response)
            try:
                return json.loads(content)
            except Exception:
                # Fallback: extract first JSON block via regex
                match = re.search(r"\{.*\}", str(content), re.DOTALL)
                if match:
                    return json.loads(match.group(0))
                raise ValueError(f"Ollama response could not be parsed as JSON: {content}")

        response = self.llm.invoke(messages)
        return response.content if hasattr(response, "content") else str(response)


class MockLLMClient:
    """Deterministic mock LLM provider for unit tests and offline CI."""

    def __init__(
        self,
        default_response: Optional[Union[dict[str, Any], str]] = None,
    ) -> None:
        self.responses: dict[str, Union[dict[str, Any], str]] = {}
        self.default_response: Union[dict[str, Any], str] = (
            default_response if default_response is not None else {"status": "ok", "message": "default mock response"}
        )
        self.call_history: list[dict[str, Any]] = []

    def register_response(
        self,
        pattern: str,
        response: Union[dict[str, Any], str],
    ) -> None:
        """Register a canned response triggered by a keyword or regex pattern."""
        self.responses[pattern] = response

    def complete(
        self,
        prompt: str,
        system: str = "",
        json_schema: Optional[dict[str, Any]] = None,
    ) -> Union[dict[str, Any], str]:
        """Return registered response matching prompt/system or default response."""
        self.call_history.append({
            "prompt": prompt,
            "system": system,
            "json_schema": json_schema,
        })

        full_text = f"{system}\n{prompt}"
        for pattern, canned in self.responses.items():
            if re.search(pattern, full_text, re.IGNORECASE):
                return canned

        return self.default_response


# Alias for backward compatibility
OllamaClient = OllamaLLM
