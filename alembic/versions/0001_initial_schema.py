"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-09-29

Creates all tables for the EVE Healthcare diagnostic booking service:
  - users
  - diagnostic_centres
  - diagnostic_tests
  - centre_tests          (M2M with price)
  - bookings
  - payments
  - payment_webhook_events (idempotency store)
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers used by Alembic
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ------------------------------------------------------------------
    # diagnostic_centres
    # ------------------------------------------------------------------
    op.create_table(
        "diagnostic_centres",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("location", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ------------------------------------------------------------------
    # diagnostic_tests
    # ------------------------------------------------------------------
    op.create_table(
        "diagnostic_tests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_diagnostic_tests_name", "diagnostic_tests", ["name"], unique=True)

    # ------------------------------------------------------------------
    # centre_tests  (association with price)
    # ------------------------------------------------------------------
    op.create_table(
        "centre_tests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("centre_id", sa.String(36), sa.ForeignKey("diagnostic_centres.id", ondelete="CASCADE"), nullable=False),
        sa.Column("test_id", sa.String(36), sa.ForeignKey("diagnostic_tests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("centre_id", "test_id", name="uq_centre_test"),
        sa.CheckConstraint("price > 0", name="ck_centre_test_price_positive"),
    )
    op.create_index("ix_centre_tests_centre_id", "centre_tests", ["centre_id"])
    op.create_index("ix_centre_tests_test_id", "centre_tests", ["test_id"])

    # ------------------------------------------------------------------
    # bookings
    # ------------------------------------------------------------------
    op.create_table(
        "bookings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("test_id", sa.String(36), sa.ForeignKey("diagnostic_tests.id"), nullable=False),
        sa.Column("centre_id", sa.String(36), sa.ForeignKey("diagnostic_centres.id"), nullable=False),
        sa.Column("appointment_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "CONFIRMED", "FAILED", "CANCELLED", name="bookingstatus"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_bookings_user_id", "bookings", ["user_id"])

    # ------------------------------------------------------------------
    # payments
    # ------------------------------------------------------------------
    op.create_table(
        "payments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("booking_id", sa.String(36), sa.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payment_reference", sa.String(100), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "SUCCESS", "FAILED", name="paymentstatus"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("provider_event_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("booking_id", name="uq_payment_booking"),
        sa.UniqueConstraint("payment_reference", name="uq_payment_reference"),
    )
    op.create_index("ix_payments_booking_id", "payments", ["booking_id"])
    op.create_index("ix_payments_provider_event_id", "payments", ["provider_event_id"])

    # ------------------------------------------------------------------
    # payment_webhook_events  (idempotency store)
    # ------------------------------------------------------------------
    op.create_table(
        "payment_webhook_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(255), nullable=False),   # UNIQUE — the idempotency key
        sa.Column("booking_id", sa.String(36), nullable=True),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("RECEIVED", "DUPLICATE", "FAILED", name="webhookeventstatus"),
            nullable=False,
            server_default="RECEIVED",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("event_id", name="uq_webhook_event_id"),
    )
    op.create_index("ix_webhook_event_id", "payment_webhook_events", ["event_id"], unique=True)
    op.create_index("ix_webhook_booking_id", "payment_webhook_events", ["booking_id"])


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("payment_webhook_events")
    op.drop_table("payments")
    op.drop_table("bookings")
    op.drop_table("centre_tests")
    op.drop_table("diagnostic_tests")
    op.drop_table("diagnostic_centres")
    op.drop_table("users")

    # Drop PostgreSQL enum types created above
    op.execute("DROP TYPE IF EXISTS bookingstatus")
    op.execute("DROP TYPE IF EXISTS paymentstatus")
    op.execute("DROP TYPE IF EXISTS webhookeventstatus")
