"""
User model.

Represents a registered patient/user of the system.
Email is unique — we use it as the login identifier.
Password is always stored as a bcrypt hash (never plaintext).
"""

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.base import TimestampMixin, generate_uuid


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    # hashed_password stores a bcrypt hash — NEVER the plaintext password
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # One user can have many bookings
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="user")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
