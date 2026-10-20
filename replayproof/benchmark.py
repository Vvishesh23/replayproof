"""End-to-end HTTP benchmark; writes measurements only after SQL reconciliation."""

import argparse
import json
import math
import os
import platform
import random
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import func, select, text

from replayproof.db import Session
from replayproof.models import Event
from replayproof.synthetic import generate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--streams", type=int, default=1)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--seed", type=int, default=2027)
    parser.add_argument(
        "--api-workers", type=int, required=True, help="Actual configured API worker count"
    )
    parser.add_argument("--output", type=Path, default=Path("artifacts/benchmark.json"))
    args = parser.parse_args()
    if not (1 <= args.count <= 100000 and 1 <= args.streams <= 32 and 1 <= args.concurrency <= 64):
        parser.error("Bounds: count 1..100000, streams 1..32, concurrency 1..64")
    results: list[dict[str, Any]] = []
    with httpx.Client(base_url=args.url, timeout=120) as client:
        for mode in ("ordered", "shuffled"):
            ids = []
            for _ in range(args.streams):
                response = client.post("/v1/streams", json={"symbol": "BENCH"})
                response.raise_for_status()
                ids.append(response.json()["id"])
            workload = [
                (sid, e.model_dump(mode="json"))
                for e in generate(args.seed, args.count)
                for sid in ids
            ]
            if mode == "shuffled":
                random.Random(args.seed).shuffle(workload)

            def send(item: tuple[str, dict[str, Any]]) -> tuple[float, int]:
                started = time.perf_counter()
                response = client.post(f"/v1/streams/{item[0]}/events", json=item[1])
                return time.perf_counter() - started, response.status_code

            started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
                samples = list(pool.map(send, workload))
            elapsed = time.perf_counter() - started
            latencies = sorted(sample[0] for sample in samples)
            errors = sum(code != 200 for _, code in samples)
            reports = []
            for sid in ids:
                response = client.post(f"/v1/streams/{sid}/reconcile")
                response.raise_for_status()
                report = response.json()
                assert report["status"] == "matched" and report["observed_cursor"] == args.count
                with Session() as session:
                    count = session.scalar(
                        select(func.count()).select_from(Event).where(Event.stream_id == UUID(sid))
                    )
                assert count == args.count
                report["source_event_count"] = count
                reports.append(report)
            assert not errors
            results.append(
                {
                    "mode": mode,
                    "elapsed_seconds": elapsed,
                    "events_per_second": len(samples) / elapsed,
                    "p50_seconds": latencies[math.ceil(len(samples) * 0.50) - 1],
                    "p95_seconds": latencies[math.ceil(len(samples) * 0.95) - 1],
                    "p99_seconds": latencies[math.ceil(len(samples) * 0.99) - 1],
                    "errors": errors,
                    "conflicts": sum(code == 409 for _, code in samples),
                    "samples": samples,
                    "reconciliation": reports,
                }
            )
    assert len({r["digest"] for result in results for r in result["reconciliation"]}) == 1
    with Session() as session:
        postgres = session.scalar(text("SELECT version()"))
    payload = {
        "parameters": {k: str(v) for k, v in vars(args).items()},
        "platform": platform.platform(),
        "python": platform.python_version(),
        "logical_processors": os.cpu_count(),
        "processor": platform.processor(),
        "postgres": postgres,
        "preconditioning": "new streams; existing database and connection cache",
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
