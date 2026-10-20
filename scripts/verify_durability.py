"""Capture/compare demo state across an operator-controlled PostgreSQL restart."""

import argparse
import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from replayproof.db import Session
from replayproof.models import Event
from replayproof.service import actual, digest, lock


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["capture", "verify"])
    parser.add_argument("--incident", type=Path, default=Path("artifacts/demo/incident.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/verification"))
    args = parser.parse_args()
    incident = json.loads(args.incident.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    state = []
    for value in incident["stream_ids"]:
        sid = UUID(value)
        with Session.begin() as session:
            stream = lock(session, sid)
            rows = list(
                session.execute(
                    select(Event.sequence, Event.payload_sha256)
                    .where(Event.stream_id == sid)
                    .order_by(Event.sequence)
                )
            )
            state.append(
                {
                    "stream_id": value,
                    "cursor": stream.last_applied_seq,
                    "max_received_seq": stream.max_received_seq,
                    "source_fingerprints": [list(row) for row in rows],
                    "projection_digest": digest(actual(session, sid)),
                }
            )
    path = args.output_dir / "durability-before.json"
    if args.mode == "capture":
        path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        print("Captured canonical fingerprints, cursors and projection digests")
    else:
        assert state == json.loads(path.read_text(encoding="utf-8"))
        (args.output_dir / "durability-after.json").write_text(
            json.dumps(
                {
                    "matched": True,
                    "streams": len(state),
                    "source_events": sum(len(s["source_fingerprints"]) for s in state),
                    "state": state,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print("PASS: source fingerprints, cursors and bar digests survived database restart")


if __name__ == "__main__":
    main()
