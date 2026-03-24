"""Unit tests for the ProfileAttributeRepository."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.models.user import User
from coyo.models.user_profile_attribute import UserProfileAttribute
from coyo.repositories.profile_attribute import ProfileAttributeRepository


class TestGetAllForUser:
    """Tests for ProfileAttributeRepository.get_all_for_user."""

    @pytest.mark.unit
    async def test_get_all_for_user_empty(
        self, db_session: AsyncSession, test_user: User
    ):
        """Should return empty list when user has no attributes."""
        repo = ProfileAttributeRepository(db_session)
        result = await repo.get_all_for_user(test_user.id)
        assert result == []

    @pytest.mark.unit
    async def test_get_all_for_user_returns_all(
        self, db_session: AsyncSession, test_user: User
    ):
        """Should return all attributes for the user."""
        repo = ProfileAttributeRepository(db_session)

        attr1 = UserProfileAttribute(
            user_id=test_user.id,
            key="job_industry",
            value="IT",
            confidence=0.9,
        )
        attr2 = UserProfileAttribute(
            user_id=test_user.id,
            key="hometown_or_location",
            value="Tokyo",
            confidence=0.8,
        )
        db_session.add_all([attr1, attr2])
        await db_session.flush()

        result = await repo.get_all_for_user(test_user.id)
        assert len(result) == 2
        keys = {a.key for a in result}
        assert keys == {"job_industry", "hometown_or_location"}


class TestUpsert:
    """Tests for ProfileAttributeRepository.upsert."""

    @pytest.mark.unit
    async def test_upsert_creates_new(
        self, db_session: AsyncSession, test_user: User
    ):
        """Should insert a new attribute when none exists."""
        repo = ProfileAttributeRepository(db_session)

        result = await repo.upsert(
            user_id=test_user.id,
            key="job_industry",
            value="Software Engineering",
            confidence=0.9,
        )

        assert result.value == "Software Engineering"
        assert result.confidence == 0.9

        # Verify it is in the database
        stmt = select(UserProfileAttribute).where(
            UserProfileAttribute.user_id == test_user.id,
            UserProfileAttribute.key == "job_industry",
        )
        db_result = await db_session.execute(stmt)
        attr = db_result.scalar_one()
        assert attr.value == "Software Engineering"

    @pytest.mark.unit
    async def test_upsert_updates_existing(
        self, db_session: AsyncSession, test_user: User
    ):
        """Should update an existing attribute."""
        repo = ProfileAttributeRepository(db_session)

        # Create initial attribute
        attr = UserProfileAttribute(
            user_id=test_user.id,
            key="job_industry",
            value="IT",
            confidence=0.6,
        )
        db_session.add(attr)
        await db_session.flush()

        # Upsert with new value
        result = await repo.upsert(
            user_id=test_user.id,
            key="job_industry",
            value="Software Engineering",
            confidence=0.9,
        )

        assert result.value == "Software Engineering"
        assert result.confidence == 0.9

        # Verify only one record exists
        stmt = select(UserProfileAttribute).where(
            UserProfileAttribute.user_id == test_user.id,
            UserProfileAttribute.key == "job_industry",
        )
        db_result = await db_session.execute(stmt)
        attrs = db_result.scalars().all()
        assert len(attrs) == 1
        assert attrs[0].value == "Software Engineering"


class TestDelete:
    """Tests for ProfileAttributeRepository.delete."""

    @pytest.mark.unit
    async def test_delete_returns_true_when_found(
        self, db_session: AsyncSession, test_user: User
    ):
        """Should return True when attribute is successfully deleted."""
        repo = ProfileAttributeRepository(db_session)

        attr = UserProfileAttribute(
            user_id=test_user.id,
            key="family_status",
            value="Married",
            confidence=0.8,
        )
        db_session.add(attr)
        await db_session.flush()

        result = await repo.delete(test_user.id, "family_status")
        assert result is True

        # Verify it is deleted
        stmt = select(UserProfileAttribute).where(
            UserProfileAttribute.user_id == test_user.id,
            UserProfileAttribute.key == "family_status",
        )
        db_result = await db_session.execute(stmt)
        assert db_result.scalar_one_or_none() is None

    @pytest.mark.unit
    async def test_delete_returns_false_when_not_found(
        self, db_session: AsyncSession, test_user: User
    ):
        """Should return False when attribute does not exist."""
        repo = ProfileAttributeRepository(db_session)

        result = await repo.delete(test_user.id, "nonexistent_key")
        assert result is False


class TestGetByKey:
    """Tests for ProfileAttributeRepository.get_by_key."""

    @pytest.mark.unit
    async def test_get_by_key_found(
        self, db_session: AsyncSession, test_user: User
    ):
        """Should return the attribute when found."""
        repo = ProfileAttributeRepository(db_session)

        attr = UserProfileAttribute(
            user_id=test_user.id,
            key="job_industry",
            value="IT",
            confidence=0.9,
        )
        db_session.add(attr)
        await db_session.flush()

        result = await repo.get_by_key(test_user.id, "job_industry")
        assert result is not None
        assert result.value == "IT"

    @pytest.mark.unit
    async def test_get_by_key_not_found(
        self, db_session: AsyncSession, test_user: User
    ):
        """Should return None when attribute does not exist."""
        repo = ProfileAttributeRepository(db_session)

        result = await repo.get_by_key(test_user.id, "nonexistent_key")
        assert result is None
