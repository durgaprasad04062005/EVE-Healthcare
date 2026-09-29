"""
Application entry point.

Responsibilities here are minimal:
- Create the FastAPI app instance
- Register routers
- Configure logging
- Add startup/shutdown hooks

Business logic belongs in services, not here.
"""

from fastapi import FastAPI

from app.core.logging import configure_logging
from app.api import auth as auth_router
from app.api import centres as centres_router
from app.api import tests as tests_router
from app.api import bookings as bookings_router
from app.api import payments as payments_router

configure_logging()

app = FastAPI(
    title="EVE Healthcare API",
    description=(
        "Backend service for diagnostic test bookings and simulated payments. "
        "Built as part of the EVE Healthcare SDE Intern Assignment."
    ),
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Returns 200 OK if the service is running."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth_router.router,     prefix="/auth",     tags=["auth"])
app.include_router(centres_router.router,  prefix="/centres",  tags=["centres"])
app.include_router(tests_router.router,    prefix="/tests",    tags=["tests"])
app.include_router(bookings_router.router, prefix="/bookings", tags=["bookings"])
app.include_router(payments_router.router, prefix="/payments", tags=["payments"])
