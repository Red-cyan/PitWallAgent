from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import asdict, dataclass

import httpx


@dataclass(frozen=True)
class Sample:
    latency_ms: float
    status_code: int | None
    ttft_ms: float | None = None
    error: str | None = None


async def run_sample(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    *,
    mode: str,
    question: str,
) -> Sample:
    async with semaphore:
        started = time.perf_counter()
        try:
            if mode in {"live", "ready"}:
                response = await client.get(f"/health/{mode}")
                response.raise_for_status()
                return Sample(elapsed_ms(started), response.status_code)
            if mode == "retrieval":
                response = await client.post(
                    "/api/rules/retrieve/debug",
                    json={"question": question, "top_k": 5},
                )
                response.raise_for_status()
                return Sample(elapsed_ms(started), response.status_code)

            first_token_at: float | None = None
            async with client.stream("POST", "/api/chat/stream", json={"message": question}) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line == "event: message_delta" and first_token_at is None:
                        first_token_at = time.perf_counter()
            return Sample(
                elapsed_ms(started),
                response.status_code,
                (first_token_at - started) * 1000 if first_token_at else None,
            )
        except Exception as exc:
            return Sample(elapsed_ms(started), None, error=exc.__class__.__name__)


def elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(round((len(ordered) - 1) * fraction), len(ordered) - 1)
    return ordered[index]


async def benchmark(args: argparse.Namespace) -> dict:
    semaphore = asyncio.Semaphore(args.concurrency)
    timeout = httpx.Timeout(args.timeout)
    started = time.perf_counter()
    async with httpx.AsyncClient(base_url=args.base_url, timeout=timeout) as client:
        samples = await asyncio.gather(*[
            run_sample(client, semaphore, mode=args.mode, question=args.question)
            for _ in range(args.requests)
        ])
    wall_seconds = time.perf_counter() - started
    latencies = [sample.latency_ms for sample in samples if sample.error is None]
    ttfts = [sample.ttft_ms for sample in samples if sample.ttft_ms is not None]
    result = {
        "mode": args.mode,
        "base_url": args.base_url,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "successes": len(latencies),
        "errors": len(samples) - len(latencies),
        "requests_per_second": round(len(latencies) / wall_seconds, 2) if wall_seconds else 0.0,
        "p50_latency_ms": round(statistics.median(latencies), 2) if latencies else 0.0,
        "p95_latency_ms": round(percentile(latencies, 0.95), 2),
        "p50_ttft_ms": round(statistics.median(ttfts), 2) if ttfts else None,
        "p95_ttft_ms": round(percentile(ttfts, 0.95), 2) if ttfts else None,
    }
    if args.include_samples:
        result["samples"] = [asdict(sample) for sample in samples]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded async benchmark against PitWall APIs.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--mode", choices=("live", "ready", "retrieval", "stream"), default="live")
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--question", default="What does B5.6.4 require?")
    parser.add_argument("--max-p95-ms", type=float)
    parser.add_argument("--include-samples", action="store_true")
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        parser.error("requests and concurrency must be positive")

    result = asyncio.run(benchmark(args))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["errors"]:
        return 1
    if args.max_p95_ms is not None and result["p95_latency_ms"] > args.max_p95_ms:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
