"""Provenance tracking for tool calls and observed entity identifiers."""

from typing import Any


class ToolCallLog:
    """Records tool calls during agent execution and collects observed strings."""

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def record(self, tool_name: str, args: dict, result: Any) -> None:
        """Record an executed tool call and its result."""
        self.entries.append({
            "tool_name": tool_name,
            "args": args,
            "result": result,
        })

    def observed_strings(self) -> set[str]:
        """Collect every string found anywhere in recorded results (walk dicts/lists/tuples recursively)."""
        observed: set[str] = set()

        def _walk(val: Any) -> None:
            if isinstance(val, str):
                observed.add(val)
            elif isinstance(val, dict):
                for k, v in val.items():
                    if isinstance(k, str):
                        observed.add(k)
                    _walk(v)
            elif isinstance(val, (list, tuple, set)):
                for item in val:
                    _walk(item)
            elif hasattr(val, "__dict__"):
                _walk(vars(val))

        for entry in self.entries:
            _walk(entry["result"])

        return observed
