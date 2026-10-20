from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from replayproof.db import Base


class Stream(Base):
    __tablename__ = "streams"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(String(20))
    last_applied_seq: Mapped[int] = mapped_column(BigInteger, default=0)
    max_received_seq: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        CheckConstraint("last_applied_seq >= 0 AND max_received_seq >= last_applied_seq"),
    )


class Event(Base):
    __tablename__ = "source_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    stream_id: Mapped[UUID] = mapped_column(ForeignKey("streams.id"))
    sequence: Mapped[int] = mapped_column(BigInteger)
    source_event_id: Mapped[str] = mapped_column(String(80))
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    price_ticks: Mapped[int] = mapped_column(BigInteger)
    quantity: Mapped[int] = mapped_column(BigInteger)
    schema_version: Mapped[int]
    payload_sha256: Mapped[str] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    __table_args__ = (
        UniqueConstraint("stream_id", "sequence"),
        UniqueConstraint("stream_id", "source_event_id"),
        CheckConstraint("sequence > 0 AND price_ticks > 0 AND quantity > 0 AND schema_version = 1"),
        Index("ix_events_stream_time", "stream_id", "event_time"),
    )


class Bar(Base):
    __tablename__ = "bars"
    stream_id: Mapped[UUID] = mapped_column(ForeignKey("streams.id"), primary_key=True)
    minute_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[int] = mapped_column(BigInteger)
    high: Mapped[int] = mapped_column(BigInteger)
    low: Mapped[int] = mapped_column(BigInteger)
    close: Mapped[int] = mapped_column(BigInteger)
    volume: Mapped[int] = mapped_column(BigInteger)
    trade_count: Mapped[int] = mapped_column(BigInteger)
    __table_args__ = (
        CheckConstraint(
            'low > 0 AND high >= low AND "open" BETWEEN low AND high AND "close" BETWEEN low AND high AND volume > 0 AND trade_count > 0'
        ),
    )


class Conflict(Base):
    __tablename__ = "integrity_conflicts"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    stream_id: Mapped[UUID] = mapped_column(ForeignKey("streams.id"), index=True)
    sequence: Mapped[int] = mapped_column(BigInteger)
    category: Mapped[str]
    reason: Mapped[str]
    original_sha256: Mapped[str]
    incoming_sha256: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Run(Base):
    __tablename__ = "reconciliation_runs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    stream_id: Mapped[UUID] = mapped_column(ForeignKey("streams.id"))
    observed_cursor: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str]
    digest: Mapped[str]
    expected_count: Mapped[int]
    mismatch_count: Mapped[int]
    diffs: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
