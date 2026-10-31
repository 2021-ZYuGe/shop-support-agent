from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, field_serializer


class UtcSerializationModel(BaseModel):
    @field_serializer(
        "expires_at",
        "placed_at",
        "delivered_at",
        "generated_at",
        "created_at",
        "updated_at",
        check_fields=False,
    )
    def serialize_utc_datetime(self, value: datetime | None, _info: Any) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
