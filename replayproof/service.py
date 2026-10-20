import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, or_, select, text
from sqlalchemy.orm import Session

from replayproof.contracts import EventInput
from replayproof.models import Bar, Conflict, Event, Run, Stream

FIELDS = ("open", "high", "low", "close", "volume", "trade_count")
PRICE_SCALE = 10000


def lock(session: Session, stream_id: UUID) -> Stream:
    stream = session.scalar(select(Stream).where(Stream.id == stream_id).with_for_update())
    if stream is None:
        raise HTTPException(404, "Stream not found")
    return stream


def minute(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(second=0, microsecond=0)


def reduce_events(events: list[Event]) -> dict[str, int]:
    ordered = sorted(events, key=lambda event: (event.event_time, event.sequence))
    return {
        "open": ordered[0].price_ticks,
        "close": ordered[-1].price_ticks,
        "high": max(e.price_ticks for e in ordered),
        "low": min(e.price_ticks for e in ordered),
        "volume": sum(e.quantity for e in ordered),
        "trade_count": len(ordered),
    }


def ingest(session: Session, stream_id: UUID, incoming: EventInput) -> dict[str, Any]:
    # Caller owns the transaction. Conflict is a return value so audit commits.
    stream = lock(session, stream_id)
    fingerprint = incoming.fingerprint(stream_id)
    existing = list(
        session.scalars(
            select(Event).where(
                Event.stream_id == stream_id,
                or_(
                    Event.sequence == incoming.sequence,
                    Event.source_event_id == incoming.source_event_id,
                ),
            )
        )
    )
    if existing:
        original = next(
            (event for event in existing if event.sequence == incoming.sequence), existing[0]
        )
        if original.sequence == incoming.sequence and original.payload_sha256 == fingerprint:
            return {"status": "duplicate", "cursor": stream.last_applied_seq}
        category = (
            "sequence_payload" if original.sequence == incoming.sequence else "source_identity"
        )
        session.add(
            Conflict(
                stream_id=stream_id,
                sequence=incoming.sequence,
                category=category,
                reason="Canonical identity cannot be replaced",
                original_sha256=original.payload_sha256,
                incoming_sha256=fingerprint,
            )
        )
        return {"status": "conflict", "category": category, "cursor": stream.last_applied_seq}
    session.add(Event(stream_id=stream_id, payload_sha256=fingerprint, **incoming.model_dump()))
    session.flush()
    stream.max_received_seq = max(stream.max_received_seq, incoming.sequence)
    pending = list(
        session.scalars(
            select(Event)
            .where(Event.stream_id == stream_id, Event.sequence > stream.last_applied_seq)
            .order_by(Event.sequence)
        )
    )
    touched = set()
    for event in pending:
        if event.sequence != stream.last_applied_seq + 1:
            break
        stream.last_applied_seq = event.sequence
        touched.add(minute(event.event_time))
    if touched:
        # One bounded range query; group only touched minutes in memory.
        applied = session.scalars(
            select(Event).where(
                Event.stream_id == stream_id,
                Event.sequence <= stream.last_applied_seq,
                Event.event_time >= min(touched),
                Event.event_time < max(touched) + timedelta(minutes=1),
            )
        )
        groups: dict[datetime, list[Event]] = {bucket: [] for bucket in touched}
        for event in applied:
            bucket = minute(event.event_time)
            if bucket in groups:
                groups[bucket].append(event)
        for bucket, events in groups.items():
            bar = session.get(Bar, (stream_id, bucket))
            if bar is None:
                session.add(Bar(stream_id=stream_id, minute_start=bucket, **reduce_events(events)))
            else:
                for field, value in reduce_events(events).items():
                    setattr(bar, field, value)
    session.flush()
    return {
        "status": "applied" if incoming.sequence <= stream.last_applied_seq else "buffered",
        "cursor": stream.last_applied_seq,
    }


def normalize(rows: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "minute_start": row.minute_start.astimezone(UTC).isoformat(),
            **{field: int(getattr(row, field)) for field in FIELDS},
        }
        for row in rows
    ]


def digest(rows: list[dict[str, Any]]) -> str:
    return hashlib.sha256(
        json.dumps(
            {"price_scale": PRICE_SCALE, "bars": rows}, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def actual(session: Session, stream_id: UUID) -> list[dict[str, Any]]:
    return normalize(
        list(
            session.scalars(
                select(Bar).where(Bar.stream_id == stream_id).order_by(Bar.minute_start)
            )
        )
    )


ORACLE = text("""
WITH ranked AS (
 SELECT date_trunc('minute', event_time AT TIME ZONE 'UTC') AT TIME ZONE 'UTC' AS minute_start,
 price_ticks, quantity,
 row_number() OVER (PARTITION BY date_trunc('minute', event_time AT TIME ZONE 'UTC')
                    ORDER BY event_time, sequence) AS first_rank,
 row_number() OVER (PARTITION BY date_trunc('minute', event_time AT TIME ZONE 'UTC')
                    ORDER BY event_time DESC, sequence DESC) AS last_rank
 FROM source_events WHERE stream_id = :stream_id AND sequence <= :cursor
)
SELECT minute_start, max(price_ticks) FILTER (WHERE first_rank = 1) AS open,
 max(price_ticks) AS high, min(price_ticks) AS low,
 max(price_ticks) FILTER (WHERE last_rank = 1) AS close,
 sum(quantity) AS volume, count(*) AS trade_count
FROM ranked GROUP BY minute_start ORDER BY minute_start
""")


def expected(session: Session, stream: Stream) -> list[dict[str, Any]]:
    return normalize(
        list(session.execute(ORACLE, {"stream_id": stream.id, "cursor": stream.last_applied_seq}))
    )


def reconcile(session: Session, stream_id: UUID) -> Run:
    stream = lock(session, stream_id)
    reference, observed = expected(session, stream), actual(session, stream_id)
    left = {r["minute_start"]: r for r in reference}
    right = {r["minute_start"]: r for r in observed}
    diffs = [
        {"minute_start": key, "expected": left.get(key), "actual": right.get(key)}
        for key in sorted(left.keys() | right.keys())
        if left.get(key) != right.get(key)
    ]
    run = Run(
        stream_id=stream_id,
        observed_cursor=stream.last_applied_seq,
        status="mismatch" if diffs else "matched",
        digest=digest(observed),
        expected_count=len(reference),
        mismatch_count=len(diffs),
        diffs=diffs,
    )
    session.add(run)
    session.flush()
    return run


def rebuild(session: Session, stream_id: UUID) -> dict[str, Any]:
    stream = lock(session, stream_id)
    before, reference = actual(session, stream_id), expected(session, stream)
    old = {r["minute_start"]: r for r in before}
    new = {r["minute_start"]: r for r in reference}
    changed = sum(old.get(k) != new.get(k) for k in old.keys() | new.keys())
    session.execute(delete(Bar).where(Bar.stream_id == stream_id))
    for row in reference:
        session.add(
            Bar(
                stream_id=stream_id,
                minute_start=datetime.fromisoformat(row["minute_start"]),
                **{field: row[field] for field in FIELDS},
            )
        )
    session.flush()
    return {
        "before_digest": digest(before),
        "after_digest": digest(reference),
        "changed_bucket_count": changed,
    }
