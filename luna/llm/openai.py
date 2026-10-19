"""OpenAI-compatible LLM provider with zero-leak key security."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
import urllib.error
from typing import Any, Callable, Optional
from luna.llm.client import LlmOutputError, extract_json_from_text, looks_like_provider_notice, run_text_tool_loop


def _mask_api_key(key: Optional[str]) -> str:
    if not key:
        return "<unset>"
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


class OpenAICompatibleLLM:
    """Provider for any OpenAI-compatible completions API (OpenAI, Groq, DeepSeek, vLLM, etc.)."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        timeout: float = 90.0,
        max_tokens: int = 4096,
    ) -> None:
        raw_url = base_url or os.getenv("LUNA_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        self.base_url = raw_url.rstrip("/")
        self._api_key = api_key or os.getenv("LUNA_LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        self.model = model or os.getenv("LUNA_LLM_MODEL") or "gpt-4o-mini"
        self.temperature = temperature
        timeout_env = os.getenv("LUNA_LLM_TIMEOUT_S")
        self.timeout = float(timeout_env) if timeout_env else timeout
        tokens_env = os.getenv("LUNA_LLM_MAX_OUTPUT_TOKENS")
        self.max_tokens = int(tokens_env) if tokens_env else max_tokens

    def info(self) -> dict[str, Any]:
        is_local = "localhost" in self.base_url or "127.0.0.1" in self.base_url
        return {
            "provider": "openai_compatible",
            "model": self.model,
            "remote": not is_local,
            "reachable": self.ping(),
        }

    def ping(self) -> bool:
        if not self._api_key and "localhost" not in self.base_url:
            return False
        try:
            req = urllib.request.Request(
                f"{self.base_url}/models",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "User-Agent": "LUNA-OS",
                },
            )
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _chat(self, payload: dict[str, Any], timeout: Optional[float] = None, attempts: int = 4) -> str:
        """POST one chat completion and return the reply text.

        Gateways that rotate models (OmniRoute combos) can hand back a provider notice such as
        "model X is no longer available" as if it were the answer. That is never a usable reply, so
        retry a few times (the next attempt usually lands on a working model) before giving up.
        """
        body = json.dumps(payload).encode("utf-8")
        effective_timeout = timeout or self.timeout
        last_notice = ""
        for attempt in range(attempts):
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                    "User-Agent": "LUNA-OS",
                },
            )
            with urllib.request.urlopen(req, timeout=effective_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices") or [{}]
            content = (choices[0].get("message") or {}).get("content") or ""
            if not looks_like_provider_notice(content):
                return content
            last_notice = content.strip()
            time.sleep(0.6 * (attempt + 1))
        if last_notice:
            raise RuntimeError(f"model route returned a provider notice instead of an answer: {last_notice[:160]}")
        return ""

    def complete_text(
        self,
        system: str,
        user: str,
        *,
        timeout: Optional[float] = None,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        payload = {
            "model": self.model,
            "stream": False,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        try:
            return self._chat(payload, timeout)
        except Exception as e:
            raise RuntimeError(f"OpenAI-compatible completion failed: {e}") from e

    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        schema_prompt = (
            f"{system}\n\n"
            f"You MUST return ONLY valid JSON matching this schema:\n"
            f"{json.dumps(schema, indent=2)}\n"
            f"Do not include any markdown fences or explanation. Return raw JSON."
        )
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": schema_prompt},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }
        raw_text = ""
        try:
            raw_text = self._chat(payload, timeout)
            return extract_json_from_text(raw_text)
        except Exception as parse_err:
            repair_user = (
                f"Your previous output failed JSON parsing with error: {parse_err}\n\n"
                f"Previous output:\n{raw_text}\n\n"
                f"Please fix formatting and return ONLY the valid JSON object conforming to:\n"
                f"{json.dumps(schema, indent=2)}"
            )
            repair_payload = {
                "model": self.model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": "You are a JSON repair assistant. Fix the JSON and return ONLY valid JSON."},
                    {"role": "user", "content": repair_user},
                ],
                "temperature": 0.0,
                "response_format": {"type": "json_object"},
            }
            try:
                return extract_json_from_text(self._chat(repair_payload, timeout))
            except Exception as final_err:
                raise LlmOutputError(
                    f"Failed to produce valid JSON after repair: {final_err}. Output was: {raw_text[:200]}"
                ) from final_err

    def run_tool_loop(
        self,
        system: str,
        user: str,
        tools: list[Any],
        call_tool: Callable[[str, dict[str, Any]], Any],
        max_steps: int = 8,
    ) -> str:
        def chat(history: list[dict[str, str]]) -> str:
            return self._chat(
                {
                    "model": self.model,
                    "stream": False,
                    "messages": history,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                }
            )

        return run_text_tool_loop(chat, system, user, tools, call_tool, max_steps=max_steps)
