"""Explicitly local helper; never exposed as an HTTP endpoint."""

import os
from uuid import UUID

from sqlalchemy import select

from replayproof.db import Session
from replayproof.models import Bar
from replayproof.service import lock


def corrupt_bar(stream_id: UUID) -> None:
    if os.getenv("REPLAYPROOF_DEV_REBUILD") != "1":
        raise RuntimeError("Set REPLAYPROOF_DEV_REBUILD=1 for local fault injection")
    with Session.begin() as session:
        lock(session, stream_id)
        bar = session.scalars(select(Bar).where(Bar.stream_id == stream_id)).first()
        if bar is None:
            raise RuntimeError("No bar to corrupt")
        bar.volume += 1
