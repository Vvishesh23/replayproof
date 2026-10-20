"""Requires a migrated disposable PostgreSQL database. Never substitutes SQLite."""

import multiprocessing
import os
import random
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import timedelta
from functools import partial
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from replayproof import service
from replayproof.api import app
from replayproof.db import Session
from replayproof.models import Bar, Event, Stream
from replayproof.synthetic import generate

pytestmark = pytest.mark.skipif(
    os.getenv("REPLAYPROOF_TEST_DATABASE") != "1",
    reason="Set REPLAYPROOF_TEST_DATABASE=1 with migrated disposable PostgreSQL",
)
client = TestClient(app)


def process_ingest(sid: UUID) -> str:
    # Spawned interpreters own independent pools/connections and no shared mutex.
    with Session.begin() as session:
        return str(service.ingest(session, sid, generate(42, 1)[0])["status"])


def source_snapshot(sid: UUID) -> list[tuple[Any, ...]]:
    with Session() as session:
        return [
            tuple(row)
            for row in session.execute(
                select(
                    Event.id,
                    Event.sequence,
                    Event.source_event_id,
                    Event.payload_sha256,
                    Event.event_time,
                    Event.price_ticks,
                    Event.quantity,
                    Event.received_at,
                )
                .where(Event.stream_id == sid)
                .order_by(Event.sequence)
            )
        ]


def test_process_duplicate_race() -> None:
    sid = new()
    with ProcessPoolExecutor(
        max_workers=4, mp_context=multiprocessing.get_context("spawn")
    ) as pool:
        statuses = list(pool.map(process_ingest, [sid] * 8))
    assert statuses.count("applied") == 1
    assert statuses.count("duplicate") == 7
    assert len(source_snapshot(sid)) == 1
    with Session.begin() as session:
        stream = service.lock(session, sid)
        assert stream.last_applied_seq == 1
        assert service.actual(session, sid) == service.expected(session, stream)


def new() -> UUID:
    response = client.post("/v1/streams", json={"symbol": "TEST"})
    assert response.status_code == 201
    return UUID(response.json()["id"])


def send(sid: UUID, event: Any) -> Any:
    return client.post(f"/v1/streams/{sid}/events", json=event.model_dump(mode="json"))


def test_gap_duplicate_conflict() -> None:
    sid = new()
    events = generate(2027, 7)
    for i in [0, 1, 3, 5, 6]:
        assert send(sid, events[i]).status_code == 200
    state = client.get(f"/v1/streams/{sid}/status").json()
    assert state["last_applied_seq"] == 2
    assert state["gaps"] == [[3, 3], [5, 5]]
    send(sid, events[2])
    send(sid, events[4])
    assert send(sid, events[0]).json()["status"] == "duplicate"
    assert send(sid, events[0].model_copy(update={"quantity": 99})).status_code == 409
    assert send(sid, events[0].model_copy(update={"sequence": 8})).status_code == 409
    with Session.begin() as session:
        stream = service.lock(session, sid)
        assert stream.last_applied_seq == 7
        assert service.actual(session, sid) == service.expected(session, stream)


def test_replay_concurrency_and_time_order() -> None:
    events = generate(2027, 30)
    # Force ties and a historical event across a minute boundary.
    events[1] = events[1].model_copy(update={"event_time": events[0].event_time})
    events[-1] = events[-1].model_copy(
        update={"event_time": events[0].event_time - timedelta(minutes=2)}
    )
    hashes = []
    for seed in range(3):
        sid = new()
        shuffled = events.copy()
        random.Random(seed).shuffle(shuffled)
        with ThreadPoolExecutor(max_workers=6) as pool:
            responses = list(pool.map(partial(send, sid), shuffled + shuffled))
        assert all(r.status_code == 200 for r in responses)
        with Session.begin() as session:
            stream = service.lock(session, sid)
            assert stream.last_applied_seq == len(events)
            rows = service.actual(session, sid)
            assert rows == service.expected(session, stream)
            assert sum(r["trade_count"] for r in rows) == len(events)
            hashes.append(service.digest(rows))
    assert len(set(hashes)) == 1


def test_rollback_and_lost_response(monkeypatch: pytest.MonkeyPatch) -> None:
    sid = new()
    event = generate(1, 1)[0]

    def fail(events: Any) -> Any:
        raise RuntimeError("deterministic projection fault")

    with monkeypatch.context() as patch:
        patch.setattr(service, "reduce_events", fail)
        with pytest.raises(RuntimeError, match="projection fault"):
            send(sid, event)
    with Session() as session:
        assert session.scalar(select(Event).where(Event.stream_id == sid)) is None
        stream = session.get(Stream, sid)
        assert stream is not None and stream.last_applied_seq == 0
    assert send(sid, event).json()["status"] == "applied"
    # Discard first response, as a disconnected client would.
    assert send(sid, event).json()["status"] == "duplicate"


def test_failure_after_first_touched_minute_rolls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    sid = new()
    events = generate(2027, 3)
    origin = events[0].event_time.replace(second=0)
    events = [
        event.model_copy(update={"event_time": origin + timedelta(minutes=i)})
        for i, event in enumerate(events)
    ]
    assert send(sid, events[0]).json()["cursor"] == 1
    assert send(sid, events[2]).json()["status"] == "buffered"
    before_source = source_snapshot(sid)
    with Session() as session:
        before_bars = service.actual(session, sid)
    reducer = service.reduce_events
    calls = 0

    def fail_second(items: list[Event]) -> dict[str, int]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("second minute fault")
        return reducer(items)

    with monkeypatch.context() as patch:
        patch.setattr(service, "reduce_events", fail_second)
        with pytest.raises(RuntimeError, match="second minute fault"):
            send(sid, events[1])
    assert calls == 2
    assert source_snapshot(sid) == before_source
    with Session() as session:
        assert service.actual(session, sid) == before_bars
        stream = session.get(Stream, sid)
        assert stream is not None and stream.last_applied_seq == 1
    assert send(sid, events[1]).json()["cursor"] == 3


@pytest.mark.parametrize("damage", ["changed", "missing", "extra"])
def test_reconcile_rebuild(damage: str) -> None:
    sid = new()
    for event in generate(2027):
        send(sid, event)
    source_before = source_snapshot(sid)
    with Session.begin() as session:
        service.lock(session, sid)
        before = service.actual(session, sid)
        bar = session.scalars(select(Bar).where(Bar.stream_id == sid)).first()
        assert bar is not None
        if damage == "changed":
            bar.volume += 1
        elif damage == "missing":
            session.execute(
                delete(Bar).where(Bar.stream_id == sid, Bar.minute_start == bar.minute_start)
            )
        else:
            session.add(
                Bar(
                    stream_id=sid,
                    minute_start=bar.minute_start + timedelta(days=1),
                    open=1,
                    high=1,
                    low=1,
                    close=1,
                    volume=1,
                    trade_count=1,
                )
            )
    with Session.begin() as session:
        assert service.reconcile(session, sid).mismatch_count == 1
        service.rebuild(session, sid)
        assert service.reconcile(session, sid).mismatch_count == 0
        assert service.actual(session, sid) == before
    assert source_snapshot(sid) == source_before


def test_concurrent_reconcile_and_independent_streams() -> None:
    ids = [new(), new()]
    events = generate(2, 15)

    def traffic(sid: UUID) -> None:
        for event in events:
            assert send(sid, event).status_code == 200

    def inspect(sid: UUID) -> None:
        for _ in events:
            response = client.post(f"/v1/streams/{sid}/reconcile")
            assert response.json()["mismatch_count"] == 0

    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks = [pool.submit(fn, sid) for sid in ids for fn in (traffic, inspect)]
        for task in tasks:
            task.result()


def test_no_inferred_tail_and_rebuild_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    sid = new()
    send(sid, generate(1, 1)[0])
    assert client.get(f"/v1/streams/{sid}/status").json()["gaps"] == []
    monkeypatch.delenv("REPLAYPROOF_DEV_REBUILD", raising=False)
    assert client.post(f"/v1/streams/{sid}/rebuild").status_code == 404
