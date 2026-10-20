from datetime import timedelta

import pytest
from pydantic import ValidationError

from replayproof.contracts import EventInput
from replayproof.synthetic import generate


@pytest.mark.parametrize(
    "field,value",
    [
        ("sequence", 0),
        ("sequence", -1),
        ("quantity", 0),
        ("price_ticks", -1),
        ("quantity", 10**13),
        ("sequence", True),
        ("source_event_id", "bad id"),
        ("event_time", "2027-01-01T00:00:00"),
        ("extra", 1),
    ],
)
def test_validation(field: str, value: object) -> None:
    payload = generate(1, 1)[0].model_dump() | {field: value}
    with pytest.raises(ValidationError):
        EventInput.model_validate(payload)


def test_utc_hash() -> None:
    from uuid import uuid4

    event = generate(2027, 1)[0]
    from datetime import timezone

    other = EventInput.model_validate(
        event.model_dump()
        | {"event_time": event.event_time.astimezone(timezone(timedelta(hours=5)))}
    )
    sid = uuid4()
    assert event.fingerprint(sid) == other.fingerprint(sid)
