"""
Shared Pydantic response shapes used across the API.

Having a consistent error response format means API consumers
(frontend, mobile, tests) can always parse errors the same way.
"""

from pydantic import BaseModel


class MessageResponse(BaseModel):
    """Generic success/info message response."""
    message: str


class ErrorDetail(BaseModel):
    """
    Standard error response body.
    Every non-2xx response from this API returns this shape.

    Example:
        {"detail": "A booking with that ID does not exist."}
    """
    detail: str
