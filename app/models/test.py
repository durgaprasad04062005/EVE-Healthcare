"""
DiagnosticTest model.

Represents a type of diagnostic test (e.g. "Full Blood Count",
"HbA1c", "Chest X-Ray"). The test itself has a name and description.

IMPORTANT DESIGN DECISION:
Price is NOT stored on this model. It lives on CentreTest instead.
Rationale: the same test (e.g. "Blood Glucose") costs R80 at one
centre and R200 at a private hospital. Price is a property of the
centre-test relationship, not the test in isolation.
"""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.base import TimestampMixin, generate_uuid


class DiagnosticTest(Base, TimestampMixin):
    __tablename__ = "diagnostic_tests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Back-reference to all CentreTest rows that offer this test
    centre_tests: Mapped[list["CentreTest"]] = relationship(
        "CentreTest", back_populates="test", cascade="all, delete-orphan"
    )
    # Bookings for this test
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="test")

    def __repr__(self) -> str:
        return f"<DiagnosticTest id={self.id} name={self.name}>"
