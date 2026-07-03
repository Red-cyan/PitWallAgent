from __future__ import annotations

import argparse
import importlib.util
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_CASES_PATH = Path("data/evals/agent_cases.jsonl")
TEST_HARNESS_PATH = Path("tests/evals/test_agent_quality_eval.py")
REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class EvalResult:
    name: str
    intent_ok: bool
    tool_ok: bool
    action_ok: bool
    answer_ok: bool
    evidence_ok: bool
    latency_ms: float
    failures: list[str]


def _load_harness() -> Any:
    sys.path.insert(0, str(REPO_ROOT))
    spec = importlib.util.spec_from_file_location("pitwall_agent_eval_harness", TEST_HARNESS_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load eval harness from {TEST_HARNESS_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["pitwall_agent_eval_harness"] = module
    spec.loader.exec_module(module)
    return module


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return ordered[lower]
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _latency_ms(trace: dict[str, Any]) -> float:
    stages = trace.get("latency_ms_by_stage", {})
    value = stages.get("agent_total")
    return float(value) if isinstance(value, int | float) else 0.0


def _evaluate_case(service: Any, case: Any, run_case: Any) -> EvalResult:
    response = run_case(service, case)
    failures: list[str] = []

    intent_ok = response.intent == case.expected_intent
    if not intent_ok:
        failures.append(f"intent expected={case.expected_intent} actual={response.intent}")

    tool_ok = response.tool_name == case.expected_tool
    if not tool_ok:
        failures.append(f"tool expected={case.expected_tool} actual={response.tool_name}")

    actual_action = response.trace.get("action")
    action_ok = actual_action == case.expected_action
    if not action_ok:
        failures.append(f"action expected={case.expected_action} actual={actual_action}")

    status_ok = True
    if case.expected_status:
        actual_status = response.trace.get("answer_status")
        status_ok = actual_status == case.expected_status
        if not status_ok:
            failures.append(f"answer_status expected={case.expected_status} actual={actual_status}")

    include_ok = all(expected in response.final_answer for expected in case.must_include)
    if not include_ok:
        missing = [expected for expected in case.must_include if expected not in response.final_answer]
        failures.append(f"missing={missing}")

    exclude_ok = all(forbidden not in response.final_answer for forbidden in case.must_not_include)
    if not exclude_ok:
        present = [forbidden for forbidden in case.must_not_include if forbidden in response.final_answer]
        failures.append(f"forbidden_present={present}")

    answer_ok = status_ok and include_ok and exclude_ok
    evidence_count = int(response.trace.get("evidence_count") or 0)
    if case.expected_status == "insufficient_evidence":
        evidence_ok = evidence_count == 0
    elif response.tool_name == "regulation_tool":
        evidence_ok = evidence_count > 0
    else:
        evidence_ok = True
    if not evidence_ok:
        failures.append(f"evidence_count={evidence_count}")

    return EvalResult(
        name=case.name,
        intent_ok=intent_ok,
        tool_ok=tool_ok,
        action_ok=action_ok,
        answer_ok=answer_ok,
        evidence_ok=evidence_ok,
        latency_ms=_latency_ms(response.trace),
        failures=failures,
    )


def _rate(results: list[EvalResult], attr: str) -> float:
    if not results:
        return 0.0
    passed = sum(1 for result in results if getattr(result, attr))
    return passed / len(results)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PitWall Agent golden evals.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args()

    harness = _load_harness()
    cases = harness.load_cases(args.cases)
    service = harness.build_service()

    results: list[EvalResult] = []
    for case in cases:
        result = _evaluate_case(service, case, harness.run_case)
        results.append(result)
        if result.failures:
            print(f"FAIL {result.name}: {'; '.join(result.failures)}")
            if args.fail_fast:
                break

    latencies = [result.latency_ms for result in results]
    print(f"cases: {len(results)}")
    print(f"intent accuracy: {_rate(results, 'intent_ok'):.2%}")
    print(f"tool accuracy: {_rate(results, 'tool_ok'):.2%}")
    print(f"action accuracy: {_rate(results, 'action_ok'):.2%}")
    print(f"answer pass rate: {_rate(results, 'answer_ok'):.2%}")
    print(f"evidence pass rate: {_rate(results, 'evidence_ok'):.2%}")
    print(f"p50 latency ms: {statistics.median(latencies) if latencies else 0.0:.2f}")
    print(f"p95 latency ms: {_percentile(latencies, 0.95):.2f}")

    return 0 if all(not result.failures for result in results) and len(results) == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
