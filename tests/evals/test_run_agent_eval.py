from __future__ import annotations

import subprocess
import sys


def test_run_agent_eval_outputs_summary_metrics() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/run_agent_eval.py", "--cases", "data/evals/agent_cases.jsonl"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "intent accuracy:" in result.stdout
    assert "tool accuracy:" in result.stdout
    assert "action accuracy:" in result.stdout
    assert "answer pass rate:" in result.stdout
    assert "evidence pass rate:" in result.stdout
    assert "p50 latency ms:" in result.stdout
    assert "p95 latency ms:" in result.stdout
