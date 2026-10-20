import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from replayproof import service
from replayproof.contracts import EventInput, StreamInput
from replayproof.db import Session
from replayproof.models import Bar, Conflict, Event, Run, Stream

app = FastAPI(title="ReplayProof", version="0.1.0")
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})


@app.get("/v1/streams")
def list_streams(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
) -> dict[str, Any]:
    with Session() as session:
        streams = list(
            session.scalars(
                select(Stream)
                .order_by(Stream.created_at.desc(), Stream.id)
                .limit(limit)
                .offset(offset)
            )
        )
        return {
            "streams": [
                {
                    "id": str(s.id),
                    "symbol": s.symbol,
                    "last_applied_seq": s.last_applied_seq,
                    "max_received_seq": s.max_received_seq,
                    "created_at": s.created_at,
                }
                for s in streams
            ],
            "next_offset": offset + len(streams) if len(streams) == limit else None,
        }


@app.get("/v1/streams/{stream_id}/events")
def list_events(
    stream_id: UUID,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
) -> dict[str, Any]:
    with Session.begin() as session:
        stream = service.lock(session, stream_id)
        events = list(
            session.scalars(
                select(Event)
                .where(Event.stream_id == stream_id)
                .order_by(Event.sequence.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        return {
            "events": [
                {
                    "sequence": e.sequence,
                    "source_event_id": e.source_event_id,
                    "event_time": e.event_time,
                    "price_ticks": e.price_ticks,
                    "quantity": e.quantity,
                    "payload_sha256": e.payload_sha256,
                    "received_at": e.received_at,
                    "state": "applied" if e.sequence <= stream.last_applied_seq else "buffered",
                }
                for e in events
            ],
            "cursor": stream.last_applied_seq,
            "next_offset": offset + len(events) if len(events) == limit else None,
        }


@app.get("/v1/streams/{stream_id}/reconciliations")
def list_reconciliations(
    stream_id: UUID,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    with Session.begin() as session:
        service.lock(session, stream_id)
        runs = session.scalars(
            select(Run)
            .where(Run.stream_id == stream_id)
            .order_by(Run.created_at.desc(), Run.id)
            .limit(limit)
        )
        return {"runs": [report(run) for run in runs]}


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
def ready() -> dict[str, str]:
    try:
        with Session() as session:
            session.execute(text("SELECT 1 FROM alembic_version"))
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Database not ready") from exc
    return {"status": "ready"}


@app.post("/v1/streams", status_code=201)
def create_stream(payload: StreamInput) -> dict[str, Any]:
    with Session.begin() as session:
        stream = Stream(symbol=payload.symbol)
        session.add(stream)
        session.flush()
        return {"id": stream.id, "symbol": stream.symbol}


@app.post("/v1/streams/{stream_id}/events")
def event(stream_id: UUID, payload: EventInput) -> Any:
    with Session.begin() as session:
        result = service.ingest(session, stream_id, payload)
    return JSONResponse(result, status_code=409 if result["status"] == "conflict" else 200)


@app.get("/v1/streams/{stream_id}/status")
def status(stream_id: UUID) -> dict[str, Any]:
    with Session.begin() as session:
        stream = service.lock(session, stream_id)
        seqs = list(
            session.scalars(
                select(Event.sequence)
                .where(Event.stream_id == stream_id, Event.sequence > stream.last_applied_seq)
                .order_by(Event.sequence)
            )
        )
        gaps = []
        previous = stream.last_applied_seq
        for sequence in seqs:
            if sequence > previous + 1:
                gaps.append([previous + 1, sequence - 1])
            previous = sequence
        conflicts = session.scalar(
            select(func.count()).select_from(Conflict).where(Conflict.stream_id == stream_id)
        )
        event_times = session.execute(
            select(func.min(Event.event_time), func.max(Event.event_time)).where(
                Event.stream_id == stream_id
            )
        ).one()
        return {
            "last_applied_seq": stream.last_applied_seq,
            "max_received_seq": stream.max_received_seq,
            "buffered_count": len(seqs),
            "gaps": gaps,
            "blocked_by_gaps": bool(gaps),
            "conflict_count": conflicts,
            "source_event_count": stream.last_applied_seq + len(seqs),
            "first_event_time": event_times[0],
            "last_event_time": event_times[1],
        }


@app.get("/v1/streams/{stream_id}/bars")
def bars(
    stream_id: UUID,
    start: datetime,
    end: datetime,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
) -> dict[str, Any]:
    if (
        start.tzinfo is None
        or end.tzinfo is None
        or start >= end
        or end - start > timedelta(days=31)
    ):
        raise HTTPException(422, "Use aware start < end with range at most 31 days")
    with Session.begin() as session:
        service.lock(session, stream_id)
        rows = list(
            session.scalars(
                select(Bar)
                .where(
                    Bar.stream_id == stream_id, Bar.minute_start >= start, Bar.minute_start < end
                )
                .order_by(Bar.minute_start)
                .limit(limit)
                .offset(offset)
            )
        )
        return {
            "bars": service.normalize(rows),
            "provisional": True,
            "price_scale": service.PRICE_SCALE,
            "next_offset": offset + len(rows) if len(rows) == limit else None,
        }


def report(run: Run) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "stream_id": str(run.stream_id),
        "observed_cursor": run.observed_cursor,
        "status": run.status,
        "digest": run.digest,
        "expected_count": run.expected_count,
        "mismatch_count": run.mismatch_count,
        "diffs": run.diffs[:100],
        "diffs_truncated": len(run.diffs) > 100,
        "created_at": run.created_at,
    }


@app.post("/v1/streams/{stream_id}/reconcile")
def reconcile(stream_id: UUID) -> dict[str, Any]:
    with Session.begin() as session:
        return report(service.reconcile(session, stream_id))


@app.get("/v1/reconciliations/{run_id}")
def get_report(run_id: UUID) -> dict[str, Any]:
    with Session() as session:
        run = session.get(Run, run_id)
        if run is None:
            raise HTTPException(404, "Report not found")
        return report(run)


@app.post("/v1/streams/{stream_id}/rebuild")
def rebuild(stream_id: UUID) -> dict[str, Any]:
    if os.getenv("REPLAYPROOF_DEV_REBUILD") != "1":
        raise HTTPException(404, "Not found")
    with Session.begin() as session:
        return service.rebuild(session, stream_id)
