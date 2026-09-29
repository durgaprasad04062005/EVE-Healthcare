"""
DiagnosticCentre model.

Represents a physical location (lab, clinic, hospital) that offers
diagnostic tests. A centre can offer many tests, and a test can be
offered by many centres — this M2M relationship is managed through
the CentreTest association table.
"""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.base import TimestampMixin, generate_uuid


class DiagnosticCentre(Base, TimestampMixin):
    __tablename__ = "diagnostic_centres"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Back-reference to the CentreTest association rows for this centre
    centre_tests: Mapped[list["CentreTest"]] = relationship(
        "CentreTest", back_populates="centre", cascade="all, delete-orphan"
    )
    # Bookings made at this centre
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="centre")

    def __repr__(self) -> str:
        return f"<DiagnosticCentre id={self.id} name={self.name}>"
