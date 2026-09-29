"""
Pydantic schemas for Diagnostic Centres and the CentreTest association.
"""

from decimal import Decimal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Diagnostic Centre schemas
# ---------------------------------------------------------------------------

class CentreCreate(BaseModel):
    """Request body for creating a new diagnostic centre."""
    name: str = Field(..., min_length=1, max_length=255)
    location: str = Field(..., min_length=1, max_length=500)
    description: str | None = Field(None, max_length=2000)


class CentreUpdate(BaseModel):
    """Request body for updating a centre. All fields are optional."""
    name: str | None = Field(None, min_length=1, max_length=255)
    location: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = Field(None, max_length=2000)


class CentreResponse(BaseModel):
    """Public representation of a diagnostic centre."""
    id: str
    name: str
    location: str
    description: str | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# CentreTest (the M2M with price) schemas
# ---------------------------------------------------------------------------

class CentreTestAdd(BaseModel):
    """
    Request body for adding a test to a centre.
    Price is set here because it's centre-specific.
    """
    price: Decimal = Field(..., gt=0, description="Price in ZAR. Must be positive.")


class CentreTestUpdate(BaseModel):
    """Request body to update the price of a test at a centre."""
    price: Decimal = Field(..., gt=0)


class CentreTestResponse(BaseModel):
    """
    Represents a test offered by a specific centre, including the centre-specific price.
    Returned by GET /centres/{centre_id}/tests
    """
    centre_test_id: str  # the CentreTest row id
    test_id: str
    test_name: str
    test_description: str | None
    price: Decimal

    model_config = {"from_attributes": True}
