import argparse
import json
import random
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import func, select

from replayproof.db import Session
from replayproof.devtools import corrupt_bar
from replayproof.models import Event
from replayproof.service import digest
from replayproof.synthetic import generate


def demo(seed: int, url: str, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    events = generate(seed)
    with httpx.Client(base_url=url, timeout=60) as client:

        def request(method: str, path: str, **kwargs: Any) -> Any:
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()

        def stream() -> str:
            return str(request("POST", "/v1/streams", json={"symbol": "SYNTH"})["id"])

        def send(sid: str, index: int) -> Any:
            return request(
                "POST", f"/v1/streams/{sid}/events", json=events[index].model_dump(mode="json")
            )

        ordered, disrupted, concurrent = stream(), stream(), stream()
        for i in range(len(events)):
            send(ordered, i)
        arrivals = [i for i in range(len(events)) if i != 2]
        random.Random(seed).shuffle(arrivals)
        for i in arrivals:
            send(disrupted, i)
        blocked = request("GET", f"/v1/streams/{disrupted}/status")
        assert blocked["last_applied_seq"] == 2
        send(disrupted, 2)
        retry = send(disrupted, 2)
        conflict = events[2].model_dump(mode="json") | {"quantity": 999}
        response = client.post(f"/v1/streams/{disrupted}/events", json=conflict)
        assert response.status_code == 409
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda i: send(concurrent, i), arrivals + [2] + arrivals))
        corrupt_bar(UUID(disrupted))
        before = request("POST", f"/v1/streams/{disrupted}/reconcile")
        assert before["mismatch_count"] == 1
        repair = request("POST", f"/v1/streams/{disrupted}/rebuild")
        after = request("POST", f"/v1/streams/{disrupted}/reconcile")
        assert after["mismatch_count"] == 0
        hashes = []
        counts = []
        for sid in (ordered, disrupted, concurrent):
            report = request("POST", f"/v1/streams/{sid}/reconcile")
            assert report["status"] == "matched"
            bars = request(
                "GET",
                f"/v1/streams/{sid}/bars",
                params={"start": "2027-01-01T00:00:00Z", "end": "2027-01-02T00:00:00Z"},
            )["bars"]
            assert sum(b["trade_count"] for b in bars) == len(events)
            hashes.append(digest(bars))
            with Session() as session:
                source_count = session.scalar(
                    select(func.count()).select_from(Event).where(Event.stream_id == UUID(sid))
                )
            assert source_count == len(events)
            counts.append(
                {
                    "stream_id": sid,
                    "source_events": source_count,
                    "applied_trades": sum(b["trade_count"] for b in bars),
                    "bars": len(bars),
                }
            )
        assert len(set(hashes)) == 1
        evidence = {
            "incident.json": {
                "seed": seed,
                "event_count_per_stream": len(events),
                "stream_ids": [ordered, disrupted, concurrent],
                "withheld_sequence": 3,
                "blocked_status": blocked,
                "recovered_status": request("GET", f"/v1/streams/{disrupted}/status"),
                "duplicate": retry,
                "conflict": response.json(),
                "failures_injected": ["missing sequence", "bar volume +1"],
                "repair": repair,
                "outcome": "matched",
                "timestamp": datetime.now(UTC).isoformat(),
            },
            "reconciliation_before.json": before,
            "reconciliation_after.json": after,
            "digest_comparison.json": {
                "modes": ["ordered", "shuffled_gap_retry", "concurrent_duplicates"],
                "digests": hashes,
                "equal": True,
                "expected_raw_events_per_stream": len(events),
                "actual_counts": counts,
            },
        }
        for name, value in evidence.items():
            (output / name).write_text(json.dumps(value, indent=2), encoding="utf-8")
        (output / "incident.md").write_text(
            "Sequence 3 was withheld: cursor stopped at 2 while later events buffered. Normal replay recovered the prefix. A retry had no additional effect; divergent payload was audited. Local volume corruption would misstate traded volume. Independent SQL detected the exact bucket; atomic rebuild restored the matching ordered/shuffled/concurrent digests.\n",
            encoding="utf-8",
        )
        print(json.dumps(evidence, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["demo"])
    parser.add_argument("--seed", type=int, default=2027)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--output", type=Path, default=Path("artifacts/demo"))
    args = parser.parse_args()
    demo(args.seed, args.url, args.output)


if __name__ == "__main__":
    main()
