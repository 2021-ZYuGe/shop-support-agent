from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    """Return a timezone-naive UTC timestamp for MySQL DATETIME columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
