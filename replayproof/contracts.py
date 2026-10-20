import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

Positive = Annotated[int, Field(strict=True, gt=0, le=10**12)]


class StreamInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,19}$")


class EventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sequence: Positive
    source_event_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,80}$")
    event_time: AwareDatetime
    price_ticks: Positive
    quantity: Positive
    schema_version: Literal[1] = 1

    @field_validator("event_time")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    def fingerprint(self, stream_id: UUID) -> str:
        payload = self.model_dump(mode="json") | {"stream_id": str(stream_id)}
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
