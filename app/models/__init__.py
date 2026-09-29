"""
Import all models here so:
1. Alembic's env.py can import this single module and discover every table.
2. SQLAlchemy relationship() calls can resolve back-references across models.

The import order matters: models that are referenced by others should
be imported first (though SQLAlchemy handles forward references with
string names, the imports still need to happen before the session is used).
"""

from app.models.user import User
from app.models.centre import DiagnosticCentre
from app.models.test import DiagnosticTest
from app.models.centre_test import CentreTest
from app.models.booking import Booking
from app.models.payment import Payment
from app.models.webhook_event import PaymentWebhookEvent

__all__ = [
    "User",
    "DiagnosticCentre",
    "DiagnosticTest",
    "CentreTest",
    "Booking",
    "Payment",
    "PaymentWebhookEvent",
]
