"""
Pydantic schemas for the Booking resource.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models.booking import BookingStatus


class BookingCreate(BaseModel):
    """
    Request body for creating a new booking.

    The client provides:
    - Which test they want
    - Which centre they want to book at
    - When they want the appointment

    The server determines the amount from CentreTest.price.
    The client must NOT supply the amount — this prevents price manipulation.
    """
    test_id: str = Field(..., description="ID of the diagnostic test to book")
    centre_id: str = Field(..., description="ID of the diagnostic centre")
    appointment_datetime: datetime = Field(
        ...,
        description="Desired appointment date and time (must be in the future)",
    )

    @field_validator("appointment_datetime")
    @classmethod
    def appointment_must_be_future(cls, v: datetime) -> datetime:
        """Reject appointments in the past at the schema level."""
        from datetime import timezone
        now = datetime.now(timezone.utc)
        # Make naive datetimes timezone-aware for comparison
        if v.tzinfo is None:
            from datetime import timezone as tz
            v = v.replace(tzinfo=tz.utc)
        if v <= now:
            raise ValueError("Appointment datetime must be in the future")
        return v


class BookingResponse(BaseModel):
    """Public representation of a booking."""
    id: str
    user_id: str
    test_id: str
    centre_id: str
    appointment_datetime: datetime
    amount: Decimal
    status: BookingStatus

    model_config = {"from_attributes": True}
