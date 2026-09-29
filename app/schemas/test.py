"""
Pydantic schemas for Diagnostic Tests.
"""

from pydantic import BaseModel, Field


class TestCreate(BaseModel):
    """Request body for creating a new diagnostic test."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)


class TestUpdate(BaseModel):
    """Request body for updating a test. All fields are optional."""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)


class TestResponse(BaseModel):
    """Public representation of a diagnostic test (without price — price is centre-specific)."""
    id: str
    name: str
    description: str | None

    model_config = {"from_attributes": True}
