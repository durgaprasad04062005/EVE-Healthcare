"""
Catalogue service — business logic for Diagnostic Centres and Tests.

"Catalogue" is a clean name for the combined centres+tests domain.
Keeping both in one service is fine here because they are tightly
related (a centre offers tests; tests belong to centres). If this
grew, we'd split into centre_service and test_service.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.centre import DiagnosticCentre
from app.models.centre_test import CentreTest
from app.models.test import DiagnosticTest
from app.schemas.centre import CentreCreate, CentreTestAdd, CentreUpdate
from app.schemas.test import TestCreate, TestUpdate

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Centres
# ---------------------------------------------------------------------------

async def list_centres(db: AsyncSession, skip: int = 0, limit: int = 50) -> list[DiagnosticCentre]:
    """Return a paginated list of diagnostic centres."""
    result = await db.execute(
        select(DiagnosticCentre).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


async def get_centre(db: AsyncSession, centre_id: str) -> DiagnosticCentre | None:
    """Return a single centre by ID, or None if not found."""
    result = await db.execute(
        select(DiagnosticCentre).where(DiagnosticCentre.id == centre_id)
    )
    return result.scalar_one_or_none()


async def create_centre(db: AsyncSession, data: CentreCreate) -> DiagnosticCentre:
    """Create and persist a new diagnostic centre."""
    centre = DiagnosticCentre(
        name=data.name,
        location=data.location,
        description=data.description,
    )
    db.add(centre)
    await db.commit()
    await db.refresh(centre)
    logger.info("Created diagnostic centre: id=%s name=%s", centre.id, centre.name)
    return centre


async def update_centre(
    db: AsyncSession, centre: DiagnosticCentre, data: CentreUpdate
) -> DiagnosticCentre:
    """
    Update a centre with only the fields provided (partial update).
    We only set attributes that are explicitly provided in the request.
    """
    if data.name is not None:
        centre.name = data.name
    if data.location is not None:
        centre.location = data.location
    if data.description is not None:
        centre.description = data.description
    await db.commit()
    await db.refresh(centre)
    logger.info("Updated diagnostic centre: id=%s", centre.id)
    return centre


# ---------------------------------------------------------------------------
# Diagnostic Tests
# ---------------------------------------------------------------------------

async def list_tests(db: AsyncSession, skip: int = 0, limit: int = 50) -> list[DiagnosticTest]:
    """Return a paginated list of all diagnostic tests."""
    result = await db.execute(
        select(DiagnosticTest).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


async def get_test(db: AsyncSession, test_id: str) -> DiagnosticTest | None:
    """Return a single test by ID, or None if not found."""
    result = await db.execute(
        select(DiagnosticTest).where(DiagnosticTest.id == test_id)
    )
    return result.scalar_one_or_none()


async def create_test(db: AsyncSession, data: TestCreate) -> DiagnosticTest:
    """
    Create a new diagnostic test.
    :raises ValueError: if a test with the same name already exists.
    """
    # DiagnosticTest.name has a UNIQUE constraint, but we check first for
    # a cleaner error message.
    existing = await db.execute(
        select(DiagnosticTest).where(DiagnosticTest.name == data.name)
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"A diagnostic test named '{data.name}' already exists")

    test = DiagnosticTest(name=data.name, description=data.description)
    db.add(test)
    await db.commit()
    await db.refresh(test)
    logger.info("Created diagnostic test: id=%s name=%s", test.id, test.name)
    return test


async def update_test(
    db: AsyncSession, test: DiagnosticTest, data: TestUpdate
) -> DiagnosticTest:
    """Update a test with only the fields provided."""
    if data.name is not None:
        # Check uniqueness of the new name
        existing = await db.execute(
            select(DiagnosticTest).where(
                DiagnosticTest.name == data.name,
                DiagnosticTest.id != test.id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError(f"A diagnostic test named '{data.name}' already exists")
        test.name = data.name
    if data.description is not None:
        test.description = data.description
    await db.commit()
    await db.refresh(test)
    return test


# ---------------------------------------------------------------------------
# CentreTest association — adding/listing/removing tests at a centre
# ---------------------------------------------------------------------------

async def list_centre_tests(db: AsyncSession, centre_id: str) -> list[CentreTest]:
    """
    Return all CentreTest rows for a given centre, with the related
    DiagnosticTest eagerly loaded (so we can access test.name etc.).
    """
    result = await db.execute(
        select(CentreTest)
        .where(CentreTest.centre_id == centre_id)
        .options(selectinload(CentreTest.test))  # load test in the same query
    )
    return list(result.scalars().all())


async def get_centre_test(
    db: AsyncSession, centre_id: str, test_id: str
) -> CentreTest | None:
    """Return the CentreTest row for a specific centre+test pair."""
    result = await db.execute(
        select(CentreTest)
        .where(CentreTest.centre_id == centre_id, CentreTest.test_id == test_id)
        .options(selectinload(CentreTest.test))
    )
    return result.scalar_one_or_none()


async def add_test_to_centre(
    db: AsyncSession, centre_id: str, test_id: str, data: CentreTestAdd
) -> CentreTest:
    """
    Add a diagnostic test to a centre with a specific price.

    :raises ValueError: if the centre or test doesn't exist, or if the
                        test is already offered at this centre.
    """
    # Verify both exist
    centre = await get_centre(db, centre_id)
    if centre is None:
        raise ValueError(f"Diagnostic centre '{centre_id}' not found")

    test = await get_test(db, test_id)
    if test is None:
        raise ValueError(f"Diagnostic test '{test_id}' not found")

    # Check for duplicate (the DB also has a UNIQUE constraint, but we give a cleaner error)
    existing = await get_centre_test(db, centre_id, test_id)
    if existing is not None:
        raise ValueError(
            f"Test '{test.name}' is already offered at this centre. "
            "Use PUT to update the price."
        )

    ct = CentreTest(centre_id=centre_id, test_id=test_id, price=data.price)
    db.add(ct)
    await db.commit()
    await db.refresh(ct)
    # Eagerly load the test relationship for the response
    await db.refresh(ct, ["test"])
    logger.info(
        "Added test to centre: centre=%s test=%s price=%s",
        centre_id, test_id, data.price
    )
    return ct


async def update_centre_test_price(
    db: AsyncSession, centre_test: CentreTest, new_price: float
) -> CentreTest:
    """Update the price of a test at a specific centre."""
    centre_test.price = new_price
    await db.commit()
    await db.refresh(centre_test)
    await db.refresh(centre_test, ["test"])
    return centre_test


async def remove_test_from_centre(db: AsyncSession, centre_test: CentreTest) -> None:
    """Remove a test from a centre (delete the CentreTest row)."""
    await db.delete(centre_test)
    await db.commit()
    logger.info(
        "Removed test from centre: centre=%s test=%s",
        centre_test.centre_id, centre_test.test_id
    )
