"""Check that the configured LLM key and endpoint work, without printing the key.

Usage: python scripts/check_llm.py
Reads LUNA_LLM_* from the environment or .env, makes one small completion, and
reports provider, model, base URL and latency. Exit code 0 means Cases and the
investigation pipeline can call the model.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from luna.llm.factory import get_llm_client  # noqa: E402


def main() -> int:
    client = get_llm_client()
    provider = os.getenv("LUNA_LLM_PROVIDER", "ollama")
    model = getattr(client, "model", None) or os.getenv("LUNA_LLM_MODEL", "?")
    base = os.getenv("LUNA_LLM_BASE_URL", "(provider default)")
    has_key = bool(os.getenv("LUNA_LLM_API_KEY") or os.getenv("OPENAI_API_KEY"))
    print(f"provider={provider} model={model} base_url={base} api_key={'set' if has_key else 'missing'}")
    started = time.time()
    try:
        reply = client.complete_text("You are a connectivity check.", "Reply with the single word: ready")
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {type(exc).__name__}: {str(exc)[:300]}")
        return 1
    print(f"OK in {time.time() - started:.1f}s: {reply.strip()[:80]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
