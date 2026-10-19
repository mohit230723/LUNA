"""LLMClient protocol, Ollama provider, and deterministic MockLLMClient."""

from __future__ import annotations

import json
import os
import re
import urllib.request
import urllib.error
from typing import Any, Callable, Optional, Protocol, Union
from pydantic import BaseModel, Field
from luna.config import settings


class LlmOutputError(Exception):
    """Raised when LLM output cannot be parsed as JSON even after a repair attempt."""
    pass


class ToolLoopResult(BaseModel):
    """Result of executing an LLM tool loop."""
    content: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    iterations: int = 0
    raw_response: Any = None


class LLMClient(Protocol):
    """Protocol defining the interface for LLM completion requests."""

    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """Generate a strictly parsed JSON response with one repair attempt."""
        ...

    def complete_text(
        self,
        system: str,
        user: str,
        *,
        timeout: Optional[float] = None,
    ) -> str:
        """Generate a raw text response."""
        ...

    def run_tool_loop(
        self,
        system: str,
        user: str,
        tools: list[Any],
        call_tool: Callable[[str, dict[str, Any]], Any],
        max_steps: int = 8,
    ) -> str:
        """Execute a tool calling loop until resolution or max_steps."""
        ...

    def ping(self) -> bool:
        """Check if the LLM provider is reachable."""
        ...

    def info(self) -> dict[str, Any]:
        """Return provider, model, remote flag, and reachability."""
        ...



def describe_tool(t: Any) -> str:
    """Render one tool for a text tool-loop prompt.

    Accepts tool objects (name/description/parameters) and plain callables such as bound
    methods, deriving the name from __name__, the description from the docstring and the
    parameters from the signature, so models see real tool names instead of reprs.
    """
    import inspect

    name = getattr(t, "name", None) or getattr(t, "__name__", None) or str(t)
    desc = getattr(t, "description", None) or (inspect.getdoc(t) or "").strip().split(chr(10))[0]
    params = getattr(t, "parameters", None)
    if not params and callable(t):
        params = {}
        try:
            for pname, prm in inspect.signature(t).parameters.items():
                if pname in ("self", "args", "kwargs"):
                    continue
                ann = "" if prm.annotation is inspect.Parameter.empty else str(prm.annotation).replace("typing.", "")
                default = "" if prm.default is inspect.Parameter.empty else f" = {prm.default!r}"
                params[pname] = f"{ann}{default}".strip() or "any"
        except (TypeError, ValueError):
            params = {}
    return f"- {name}: {desc}" + chr(10) + f"  Parameters: {json.dumps(params or {})}"




_PROVIDER_NOTICE_RE = re.compile(
    r"no longer available|please switch to|model not found|rate.?limit|quota (exceeded|exhausted|reached)|"
    r"overloaded|try again later|temporarily unavailable|service unavailable",
    re.IGNORECASE,
)


def looks_like_provider_notice(text: str) -> bool:
    """True for an empty reply or a short provider/gateway notice that is not a real answer."""
    t = (text or "").strip()
    if not t:
        return True
    return len(t) < 400 and "{" not in t and "TOOL:" not in t and _PROVIDER_NOTICE_RE.search(t) is not None


def _balanced_object(text: str) -> Optional[str]:
    """Return the first balanced {...} JSON object in ``text`` (string-aware), or None."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def parse_tool_calls(content: str, max_calls: int = 4) -> list[tuple[str, dict[str, Any]]]:
    """Extract every ``TOOL: name`` / ``ARGS: {json}`` pair from a model reply.

    Models often batch several calls in one reply or wrap them in code fences, so all
    pairs are honoured (up to ``max_calls``) and the JSON is read with a brace-aware scan.
    """
    calls: list[tuple[str, dict[str, Any]]] = []
    for seg in re.split(r"(?=TOOL:\s*[A-Za-z0-9_-]+)", content or ""):
        m = re.match(r"TOOL:\s*([A-Za-z0-9_-]+)", seg)
        if not m:
            continue
        args: dict[str, Any] = {}
        am = re.search(r"ARGS:\s*", seg)
        if am:
            blob = _balanced_object(seg[am.end():])
            if blob:
                try:
                    parsed = json.loads(blob)
                    if isinstance(parsed, dict):
                        args = parsed
                except json.JSONDecodeError:
                    args = {}
        calls.append((m.group(1), args))
        if len(calls) >= max_calls:
            break
    return calls


def run_text_tool_loop(
    chat: Callable[[list[dict[str, str]]], str],
    system: str,
    user: str,
    tools: list[Any],
    call_tool: Callable[[str, dict[str, Any]], Any],
    max_steps: int = 8,
    max_result_chars: int = 6000,
) -> str:
    """Provider-independent tool loop over plain chat: model replies with TOOL/ARGS lines.

    Guards against the usual small-model failure modes: answering without ever calling a tool,
    batching several calls in one reply, echoing tool output as the "answer", and running out of
    steps while still asking for tools.
    """
    tools_str = "\n".join(describe_tool(t) for t in tools)
    tool_prompt = (
        f"{system}\n\n"
        f"AVAILABLE TOOLS:\n{tools_str}\n\n"
        "To call a tool, output exactly:\n"
        "TOOL: <tool_name>\n"
        "ARGS: <json_arguments>\n\n"
        "Use the exact identifiers shown in the task and in tool results (for example 'account:acc-9821-9984bf', "
        "never a shortened form). You may call several tools in one reply, one TOOL/ARGS pair after another. "
        "When you have finished gathering evidence, output ONLY your final findings JSON (no TOOL lines)."
    )
    history: list[dict[str, str]] = [
        {"role": "system", "content": tool_prompt},
        {"role": "user", "content": user},
    ]
    calls_made = 0
    nudges = 0
    for _ in range(max_steps):
        content = chat(history)
        calls = parse_tool_calls(content)
        if calls:
            history.append({"role": "assistant", "content": content})
            blocks = []
            for name, args in calls:
                try:
                    result = call_tool(name, args)
                    text = result if isinstance(result, str) else json.dumps(result, default=str)
                except Exception as ex:  # a failing tool is feedback for the model, not a crash
                    text = f"Tool execution error: {ex}"
                if len(text) > max_result_chars:
                    text = text[:max_result_chars] + " ...[truncated]"
                blocks.append(f"TOOL_RESULT ({name}):\n{text}")
                calls_made += 1
            history.append({
                "role": "user",
                "content": "\n\n".join(blocks)
                + "\n\nContinue investigating, or return ONLY your final JSON findings (no TOOL lines).",
            })
            continue
        if calls_made == 0 and nudges < 2 and tools:
            nudges += 1
            history.append({"role": "assistant", "content": content})
            history.append({
                "role": "user",
                "content": "You have not called any tool yet. Findings must come from tool output. "
                "Call a tool now using exactly:\nTOOL: <tool_name>\nARGS: <json_arguments>",
            })
            continue
        return content

    history.append({
        "role": "user",
        "content": "Tool budget used. Do NOT call any more tools. Output ONLY the final JSON findings object now.",
    })
    return chat(history)


def extract_json_from_text(text: str) -> dict[str, Any]:
    """Attempt to parse JSON from text, extracting markdown code blocks if necessary."""
    text_clean = text.strip()
    # Strip markdown code blocks if present
    if text_clean.startswith("```"):
        lines = text_clean.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text_clean = "\n".join(lines).strip()

    try:
        parsed = json.loads(text_clean)
        if isinstance(parsed, dict):
            return parsed
        elif isinstance(parsed, list):
            return {"items": parsed}
    except Exception:
        pass

    # Regex search for first balanced or curly braced JSON object
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    raise ValueError(f"Could not parse valid JSON from text: {text[:200]}...")


class OllamaLLM:
    """Ollama language model provider using native HTTP API with zero dependencies."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        timeout: float = 90.0,
        max_tokens: int = 4096,
    ) -> None:
        raw_url = base_url or os.getenv("LUNA_LLM_BASE_URL") or os.getenv("OLLAMA_BASE_URL") or settings.OLLAMA_BASE_URL
        self.base_url = raw_url.rstrip("/")
        self.model = model or os.getenv("LUNA_LLM_MODEL") or os.getenv("OLLAMA_MODEL") or settings.OLLAMA_MODEL
        self.temperature = temperature
        timeout_env = os.getenv("LUNA_LLM_TIMEOUT_S")
        self.timeout = float(timeout_env) if timeout_env else timeout
        tokens_env = os.getenv("LUNA_LLM_MAX_OUTPUT_TOKENS")
        self.max_tokens = int(tokens_env) if tokens_env else max_tokens

    def info(self) -> dict[str, Any]:
        is_local = "localhost" in self.base_url or "127.0.0.1" in self.base_url
        return {
            "provider": "ollama",
            "model": self.model,
            "remote": not is_local,
            "reachable": self.ping(),
        }

    def ping(self) -> bool:
        """Ping Ollama via /api/tags."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", headers={"User-Agent": "LUNA-OS"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
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
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }

        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "LUNA-OS"},
        )

        effective_timeout = timeout or self.timeout
        try:
            with urllib.request.urlopen(req, timeout=effective_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                msg = data.get("message", {})
                return msg.get("content", "")
        except Exception as e:
            raise RuntimeError(f"Ollama completion failed: {e}") from e

    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        # Format instruction with schema
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
            "format": "json",
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }

        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "LUNA-OS"},
        )

        effective_timeout = timeout or self.timeout
        raw_text = ""
        try:
            with urllib.request.urlopen(req, timeout=effective_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                raw_text = data.get("message", {}).get("content", "")
            return extract_json_from_text(raw_text)
        except Exception as parse_err:
            # ONE repair attempt feeding parse error back
            repair_user = (
                f"Your previous output failed JSON parsing with error: {parse_err}\n\n"
                f"Previous output:\n{raw_text}\n\n"
                f"Please fix the formatting and return ONLY the valid JSON object conforming to:\n"
                f"{json.dumps(schema, indent=2)}"
            )
            try:
                repair_payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a JSON repair assistant. Fix the JSON and return ONLY valid JSON."},
                        {"role": "user", "content": repair_user},
                    ],
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": 0.0, "num_predict": self.max_tokens},
                }
                repair_req = urllib.request.Request(
                    f"{self.base_url}/api/chat",
                    data=json.dumps(repair_payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "User-Agent": "LUNA-OS"},
                )
                with urllib.request.urlopen(repair_req, timeout=effective_timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    repaired_text = data.get("message", {}).get("content", "")
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
        """Run tool loop by formatting tools and processing calls sequentially."""
        tools_desc = [describe_tool(t) for t in tools]
        tools_str = "\n".join(tools_desc)

        tool_prompt = (
            f"{system}\n\n"
            f"AVAILABLE TOOLS:\n{tools_str}\n\n"
            f"To call a tool, output exactly:\n"
            f"TOOL: <tool_name>\n"
            f"ARGS: <json_arguments>\n\n"
            f"When you have finished gathering evidence and are ready to output findings, do NOT call a tool. "
            f"Instead output your final JSON findings directly."
        )

        history = [
            {"role": "system", "content": tool_prompt},
            {"role": "user", "content": user},
        ]

        for step in range(max_steps):
            payload = {
                "model": self.model,
                "messages": history,
                "stream": False,
                "options": {"temperature": self.temperature, "num_predict": self.max_tokens},
            }
            req = urllib.request.Request(
                f"{self.base_url}/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "LUNA-OS"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data.get("message", {}).get("content", "")

            # Check if model wants to call a tool
            tool_match = re.search(r"TOOL:\s*([A-Za-z0-9_-]+)", content)
            args_match = re.search(r"ARGS:\s*(\{.*?\})", content, re.DOTALL)

            if tool_match and args_match:
                tool_name = tool_match.group(1).strip()
                try:
                    tool_args = json.loads(args_match.group(1).strip())
                except Exception:
                    tool_args = {}

                # Execute tool
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
                # No tool call; final response reached
                return content

        # Reached max steps; request final conclusion
        history.append({
            "role": "user",
            "content": "You have reached the maximum tool steps. Return your final findings JSON now based on gathered evidence.",
        })
        payload = {
            "model": self.model,
            "messages": history,
            "stream": False,
            "options": {"temperature": self.temperature, "num_predict": self.max_tokens},
        }
        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "LUNA-OS"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("message", {}).get("content", "")


class MockLLMClient:
    """High-speed deterministic mock client for offline tests."""

    def __init__(self, model: str = "mock-v1") -> None:
        self.model = model

    def info(self) -> dict[str, Any]:
        return {
            "provider": "mock",
            "model": self.model,
            "remote": False,
            "reachable": True,
        }

    def ping(self) -> bool:
        return True

    def complete_text(self, system: str, user: str, *, timeout: Optional[float] = None) -> str:
        return "Alice Moreno is linked to Bob Chen via phone ph-ring-01 and account ba-7712."

    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        # Return canned structures matching typical schema requests
        if "tables" in schema or "mapping" in system.lower():
            return {
                "tables": [
                    {
                        "table": "cases",
                        "node_label": "Case",
                        "columns": [
                            {"column": "id", "role": "id"},
                            {"column": "name", "role": "name"},
                        ],
                    }
                ]
            }
        if "entities" in schema and "relations" in schema:
            return {
                "entities": [
                    {
                        "key": "e1",
                        "type": "Person",
                        "name": "Alice Moreno",
                        "props": {"role": "suspect"},
                        "quote": user[:50],
                        "confidence": 0.95,
                    }
                ],
                "relations": [],
            }
        if "intent" in schema:
            return {
                "intent": "who_connected",
                "mentions": ["cust-000", "Alice Moreno"],
                "constraints": {"max_hops": 3},
            }
        if "subtasks" in schema:
            return {
                "subtasks": [
                    {"capability": "trace_relationships", "goal": "Trace connections from target"}
                ]
            }
        if "findings" in schema:
            return {
                "findings": [
                    {
                        "kind": "path",
                        "claim": "Alice Moreno shares phone with Bob Chen",
                        "subject_cids": ["cust-000"],
                        "evidence_cids": ["ph-ring-01"],
                        "confidence": 0.9,
                    }
                ]
            }
        return {"result": "ok"}

    def run_tool_loop(
        self,
        system: str,
        user: str,
        tools: list[Any],
        call_tool: Callable[[str, dict[str, Any]], Any],
        max_steps: int = 8,
    ) -> str:
        # Trigger one tool call then return final JSON
        if tools:
            t_name = getattr(tools[0], "name", "neighbors")
            try:
                call_tool(t_name, {"cid": "cust-000"})
            except Exception:
                pass
        return json.dumps({
            "findings": [
                {
                    "kind": "path",
                    "claim": "Alice Moreno is connected to Bob Chen",
                    "subject_cids": ["cust-000"],
                    "evidence_cids": ["ph-ring-01"],
                    "confidence": 0.92,
                }
            ]
        })


# Backward compatibility alias
OllamaClient = OllamaLLM

