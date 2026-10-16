"""Tests for scripts/bench_llm.py local LLM benchmark (F14)."""

import sys
import subprocess
import pytest


def test_bench_llm_help() -> None:
    """Verify bench_llm.py responds to --help with exit code 0."""
    result = subprocess.run(
        [sys.executable, "scripts/bench_llm.py", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--n" in result.stdout
    assert "--markdown" in result.stdout


@pytest.mark.integration
def test_bench_llm_runs_and_exits_zero(live_store) -> None:
    """Verify bench_llm.py runs N=1 and exits 0 even if local LLM is offline or in mock."""
    result = subprocess.run(
        [sys.executable, "scripts/bench_llm.py", "--n", "1"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Runs: 1" in result.stdout or "runs" in result.stdout.lower()


@pytest.mark.integration
def test_bench_llm_markdown_output(live_store) -> None:
    """Verify bench_llm.py prints a markdown table with --markdown."""
    result = subprocess.run(
        [sys.executable, "scripts/bench_llm.py", "--n", "1", "--markdown"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "| Metric | Value |" in result.stdout
    assert "| Runs |" in result.stdout
