"""
Shared base mixin that adds id, created_at, and updated_at to every model.

Why a mixin instead of putting these on Base?
SQLAlchemy's DeclarativeBase doesn't support mixing in column definitions
directly on the base class cleanly. A separate mixin class is the idiomatic
SQLAlchemy 2.x approach.

Every model should inherit: Base, TimestampMixin (in that order)
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Adds auto-managed created_at and updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def generate_uuid() -> str:
    """Generate a new UUID4 string. Used as the default for primary keys."""
    return str(uuid.uuid4())
