import random
from datetime import UTC, datetime, timedelta

from replayproof.contracts import EventInput


def generate(seed: int, count: int = 40) -> list[EventInput]:
    rng = random.Random(seed)
    origin = datetime(2027, 1, 1, tzinfo=UTC)
    return [
        EventInput(
            sequence=i,
            source_event_id=f"synthetic-{i}",
            event_time=origin + timedelta(seconds=rng.randrange(180)),
            price_ticks=10000 + rng.randrange(100),
            quantity=rng.randrange(1, 10),
        )
        for i in range(1, count + 1)
    ]
