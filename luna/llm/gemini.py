"""Gemini LLM provider with zero-leak key security."""

from __future__ import annotations

import json
import os
import re
import urllib.request
import urllib.error
from typing import Any, Callable, Optional
from luna.llm.client import LlmOutputError, describe_tool, extract_json_from_text


def _mask_api_key(key: Optional[str]) -> str:
    if not key:
        return "<unset>"
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


class GeminiLLM:
    """Provider for Google Gemini API via REST endpoints."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.0,
        timeout: float = 90.0,
        max_tokens: int = 4096,
    ) -> None:
        self._api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("LUNA_LLM_API_KEY") or ""
        self.model = model or os.getenv("LUNA_LLM_MODEL") or "gemini-1.5-flash"
        self.base_url = (base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        self.temperature = temperature
        timeout_env = os.getenv("LUNA_LLM_TIMEOUT_S")
        self.timeout = float(timeout_env) if timeout_env else timeout
        tokens_env = os.getenv("LUNA_LLM_MAX_OUTPUT_TOKENS")
        self.max_tokens = int(tokens_env) if tokens_env else max_tokens

    def info(self) -> dict[str, Any]:
        return {
            "provider": "gemini",
            "model": self.model,
            "remote": True,
            "reachable": self.ping(),
        }

    def ping(self) -> bool:
        if not self._api_key:
            return False
        try:
            url = f"{self.base_url}/models/{self.model}?key={self._api_key}"
            req = urllib.request.Request(url, headers={"User-Agent": "LUNA-OS"})
            with urllib.request.urlopen(req, timeout=5.0) as resp:
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
        url = f"{self.base_url}/models/{self.model}:generateContent?key={self._api_key}"
        parts = []
        if system:
            parts.append({"text": f"SYSTEM: {system}\n\n"})
        parts.append({"text": user})

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
            },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "LUNA-OS"},
        )

        effective_timeout = timeout or self.timeout
        try:
            with urllib.request.urlopen(req, timeout=effective_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if candidates:
                    parts_out = candidates[0].get("content", {}).get("parts", [])
                    return "".join(p.get("text", "") for p in parts_out)
                return ""
        except Exception as e:
            raise RuntimeError(f"Gemini completion failed: {e}") from e

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

        url = f"{self.base_url}/models/{self.model}:generateContent?key={self._api_key}"
        payload = {
            "contents": [{"parts": [{"text": f"SYSTEM: {schema_prompt}\n\n{user}"}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens,
                "responseMimeType": "application/json",
            },
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "LUNA-OS"},
        )

        effective_timeout = timeout or self.timeout
        raw_text = ""
        try:
            with urllib.request.urlopen(req, timeout=effective_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if candidates:
                    parts_out = candidates[0].get("content", {}).get("parts", [])
                    raw_text = "".join(p.get("text", "") for p in parts_out)
            return extract_json_from_text(raw_text)
        except Exception as parse_err:
            repair_user = (
                f"Your previous output failed JSON parsing with error: {parse_err}\n\n"
                f"Previous output:\n{raw_text}\n\n"
                f"Please fix the formatting and return ONLY the valid JSON object conforming to:\n"
                f"{json.dumps(schema, indent=2)}"
            )
            repair_payload = {
                "contents": [{"parts": [{"text": f"SYSTEM: Fix invalid JSON and return ONLY valid JSON.\n\n{repair_user}"}]}],
                "generationConfig": {
                    "temperature": 0.0,
                    "responseMimeType": "application/json",
                },
            }
            try:
                repair_req = urllib.request.Request(
                    url,
                    data=json.dumps(repair_payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "User-Agent": "LUNA-OS"},
                )
                with urllib.request.urlopen(repair_req, timeout=effective_timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    candidates = data.get("candidates", [])
                    repaired_text = ""
                    if candidates:
                        parts_out = candidates[0].get("content", {}).get("parts", [])
                        repaired_text = "".join(p.get("text", "") for p in parts_out)
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
        tools_desc = [describe_tool(t) for t in tools]
        tools_str = "\n".join(tools_desc)

        tool_prompt = (
            f"{system}\n\n"
            f"AVAILABLE TOOLS:\n{tools_str}\n\n"
            f"To call a tool, output exactly:\n"
            f"TOOL: <tool_name>\n"
            f"ARGS: <json_arguments>\n\n"
            f"When you have finished gathering evidence, output your final findings JSON directly."
        )

        history = [{"parts": [{"text": f"SYSTEM: {tool_prompt}\n\n{user}"}]}]

        url = f"{self.base_url}/models/{self.model}:generateContent?key={self._api_key}"

        for _ in range(max_steps):
            payload = {
                "contents": history,
                "generationConfig": {
                    "temperature": self.temperature,
                    "maxOutputTokens": self.max_tokens,
                },
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "LUNA-OS"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                content = ""
                if candidates:
                    parts_out = candidates[0].get("content", {}).get("parts", [])
                    content = "".join(p.get("text", "") for p in parts_out)

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

                history.append({"role": "model", "parts": [{"text": content}]})
                history.append({
                    "role": "user",
                    "parts": [{"text": f"TOOL_RESULT ({tool_name}):\n{result_str}\n\nContinue investigating or return your final JSON findings."}],
                })
            else:
                return content

        return content
