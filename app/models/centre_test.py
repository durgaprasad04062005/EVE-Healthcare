"""
CentreTest — association table between DiagnosticCentre and DiagnosticTest.

This is the "join table with an extra column" pattern.
We use a full ORM model (not just a secondary= table) because we need
to store `price` — the price at which this particular centre offers
this particular test.

Constraints:
- (centre_id, test_id) must be UNIQUE — a centre can't list the same
  test twice with different prices. If the price changes, update the
  existing row.
- price must be positive (enforced at the application layer and by
  a CHECK constraint).
"""

from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.base import TimestampMixin, generate_uuid


class CentreTest(Base, TimestampMixin):
    __tablename__ = "centre_tests"

    # Composite unique constraint — a centre cannot offer the same test twice
    __table_args__ = (
        UniqueConstraint("centre_id", "test_id", name="uq_centre_test"),
        CheckConstraint("price > 0", name="ck_centre_test_price_positive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    centre_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("diagnostic_centres.id", ondelete="CASCADE"), nullable=False, index=True
    )
    test_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("diagnostic_tests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Numeric(10, 2) — exact decimal arithmetic for money, never Float
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    # ORM relationships
    centre: Mapped["DiagnosticCentre"] = relationship("DiagnosticCentre", back_populates="centre_tests")
    test: Mapped["DiagnosticTest"] = relationship("DiagnosticTest", back_populates="centre_tests")

    def __repr__(self) -> str:
        return f"<CentreTest centre={self.centre_id} test={self.test_id} price={self.price}>"
