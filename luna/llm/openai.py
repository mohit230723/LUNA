"""OpenAI-compatible LLM provider with zero-leak key security."""

from __future__ import annotations

import json
import os
import re
import urllib.request
import urllib.error
from typing import Any, Callable, Optional
from luna.llm.client import LlmOutputError, extract_json_from_text


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
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "User-Agent": "LUNA-OS",
            },
        )

        effective_timeout = timeout or self.timeout
        try:
            with urllib.request.urlopen(req, timeout=effective_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
                return ""
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

        messages = [
            {"role": "system", "content": schema_prompt},
            {"role": "user", "content": user},
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "response_format": {"type": "json_object"},
        }

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "User-Agent": "LUNA-OS",
            },
        )

        effective_timeout = timeout or self.timeout
        raw_text = ""
        try:
            with urllib.request.urlopen(req, timeout=effective_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                raw_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
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
                "messages": [
                    {"role": "system", "content": "You are a JSON repair assistant. Fix the JSON and return ONLY valid JSON."},
                    {"role": "user", "content": repair_user},
                ],
                "temperature": 0.0,
                "response_format": {"type": "json_object"},
            }
            try:
                repair_req = urllib.request.Request(
                    f"{self.base_url}/chat/completions",
                    data=json.dumps(repair_payload).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self._api_key}",
                        "User-Agent": "LUNA-OS",
                    },
                )
                with urllib.request.urlopen(repair_req, timeout=effective_timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    repaired_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return extract_json_from_text(repaired_text)
            except Exception as final_err:
                raise LlmOutputError(f"Failed to produce valid JSON after repair: {final_err}. Output was: {raw_text[:200]}") from final_err

    def run_tool_loop(
        self,
        system: str,
        user: str,
        tools: list[Any],
        call_tool: Callable[[str, dict[str, Any]], Any],
        max_steps: int = 8,
    ) -> str:
        tools_desc = []
        for t in tools:
            name = getattr(t, "name", str(t))
            desc = getattr(t, "description", "")
            params = getattr(t, "parameters", {})
            tools_desc.append(f"- {name}: {desc}\n  Parameters: {json.dumps(params)}")
        tools_str = "\n".join(tools_desc)

        tool_prompt = (
            f"{system}\n\n"
            f"AVAILABLE TOOLS:\n{tools_str}\n\n"
            f"To call a tool, output exactly:\n"
            f"TOOL: <tool_name>\n"
            f"ARGS: <json_arguments>\n\n"
            f"When you have finished gathering evidence, output your final findings JSON directly."
        )

        history = [
            {"role": "system", "content": tool_prompt},
            {"role": "user", "content": user},
        ]

        for _ in range(max_steps):
            payload = {
                "model": self.model,
                "messages": history,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            }
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                    "User-Agent": "LUNA-OS",
                },
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            tool_match = re.search(r"TOOL:\s*([A-Za-z0-9_-]+)", content)
            args_match = re.search(r"ARGS:\s*(\{.*?\})", content, re.DOTALL)

            if tool_match and args_match:
                tool_name = tool_match.group(1).strip()
                try:
                    tool_args = json.loads(args_match.group(1).strip())
                except Exception:
                    tool_args = {}

                try:
                    tool_result = call_tool(tool_name, tool_args)
                    result_str = json.dumps(tool_result) if not isinstance(tool_result, str) else tool_result
                except Exception as ex:
                    result_str = f"Tool execution error: {ex}"

                history.append({"role": "assistant", "content": content})
                history.append({
                    "role": "user",
                    "content": f"TOOL_RESULT ({tool_name}):\n{result_str}\n\nContinue investigating or return your final JSON findings.",
                })
            else:
                return content

        return content
