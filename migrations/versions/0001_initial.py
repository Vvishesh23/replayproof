"""Initial schema, frozen independently of application models."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None


def upgrade() -> None:
    op.create_table(
        "streams",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("last_applied_seq", sa.BigInteger(), nullable=False),
        sa.Column("max_received_seq", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("last_applied_seq >= 0 AND max_received_seq >= last_applied_seq"),
    )
    op.create_table(
        "source_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("stream_id", sa.Uuid(), sa.ForeignKey("streams.id"), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("source_event_id", sa.String(80), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price_ticks", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("stream_id", "sequence"),
        sa.UniqueConstraint("stream_id", "source_event_id"),
        sa.CheckConstraint(
            "sequence > 0 AND price_ticks > 0 AND quantity > 0 AND schema_version = 1"
        ),
    )
    op.create_index("ix_events_stream_time", "source_events", ["stream_id", "event_time"])
    op.create_table(
        "bars",
        sa.Column("stream_id", sa.Uuid(), sa.ForeignKey("streams.id"), primary_key=True),
        sa.Column("minute_start", sa.DateTime(timezone=True), primary_key=True),
        *[
            sa.Column(name, sa.BigInteger(), nullable=False)
            for name in ("open", "high", "low", "close", "volume", "trade_count")
        ],
        sa.CheckConstraint(
            'low > 0 AND high >= low AND "open" BETWEEN low AND high AND "close" BETWEEN low AND high AND volume > 0 AND trade_count > 0'
        ),
    )
    op.create_table(
        "integrity_conflicts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("stream_id", sa.Uuid(), sa.ForeignKey("streams.id"), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        *[
            sa.Column(name, sa.String(), nullable=False)
            for name in ("category", "reason", "original_sha256", "incoming_sha256")
        ],
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_integrity_conflicts_stream_id", "integrity_conflicts", ["stream_id"])
    op.create_table(
        "reconciliation_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("stream_id", sa.Uuid(), sa.ForeignKey("streams.id"), nullable=False),
        sa.Column("observed_cursor", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("digest", sa.String(), nullable=False),
        sa.Column("expected_count", sa.Integer(), nullable=False),
        sa.Column("mismatch_count", sa.Integer(), nullable=False),
        sa.Column("diffs", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    for name in ("reconciliation_runs", "integrity_conflicts", "bars", "source_events", "streams"):
        op.drop_table(name)
