from datetime import UTC, datetime

from replayproof.models import Event
from replayproof.service import digest, minute, reduce_events


def test_event_time_then_sequence_boundaries() -> None:
    later = datetime(2027, 1, 1, 0, 0, 59, tzinfo=UTC)
    earlier = later.replace(second=0)
    events = [
        Event(sequence=1, event_time=later, price_ticks=90, quantity=2),
        Event(sequence=3, event_time=earlier, price_ticks=120, quantity=3),
        Event(sequence=2, event_time=earlier, price_ticks=110, quantity=5),
    ]
    assert reduce_events(events) == {
        "open": 110,
        "close": 90,
        "high": 120,
        "low": 90,
        "volume": 10,
        "trade_count": 3,
    }
    assert minute(later) == earlier
    assert digest([{"volume": 10, "open": 110}]) == digest([{"open": 110, "volume": 10}])
