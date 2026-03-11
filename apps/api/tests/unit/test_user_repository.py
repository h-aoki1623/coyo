"""Unit tests for UserRepository auth-related methods."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.models.user import User
from coyo.repositories.user import UserRepository


class TestFindOrCreateByAuthUid:
    """Tests for UserRepository.find_or_create_by_auth_uid()."""

    @pytest.mark.unit
    async def test_creates_new_user_when_not_found(self, db_session: AsyncSession):
        repo = UserRepository(db_session)

        user = await repo.find_or_create_by_auth_uid(
            auth_uid="fb-new-uid",
            email="new@example.com",
            display_name="New User",
            auth_provider="email",
        )

        assert user.id is not None
        assert user.auth_uid == "fb-new-uid"
        assert user.email == "new@example.com"
        assert user.display_name == "New User"
        assert user.auth_provider == "email"

    @pytest.mark.unit
    async def test_returns_existing_user_when_found(self, db_session: AsyncSession):
        # Arrange: create a user with a auth_uid
        existing = User(
            auth_uid="fb-existing-uid",
            email="existing@example.com",
            display_name="Existing User",
            auth_provider="google",
        )
        db_session.add(existing)
        await db_session.commit()
        await db_session.refresh(existing)

        repo = UserRepository(db_session)

        # Act: look up the same auth_uid
        user = await repo.find_or_create_by_auth_uid(
            auth_uid="fb-existing-uid",
            email="existing@example.com",
            display_name="Existing User",
            auth_provider="google",
        )

        assert user.id == existing.id

    @pytest.mark.unit
    async def test_updates_email_when_changed(self, db_session: AsyncSession):
        existing = User(
            auth_uid="fb-uid-email-change",
            email="old@example.com",
            display_name="User",
            auth_provider="email",
        )
        db_session.add(existing)
        await db_session.commit()
        await db_session.refresh(existing)

        repo = UserRepository(db_session)

        user = await repo.find_or_create_by_auth_uid(
            auth_uid="fb-uid-email-change",
            email="new@example.com",
            display_name="User",
            auth_provider="email",
        )

        assert user.id == existing.id
        assert user.email == "new@example.com"

    @pytest.mark.unit
    async def test_updates_display_name_when_changed(self, db_session: AsyncSession):
        existing = User(
            auth_uid="fb-uid-name-change",
            email="user@example.com",
            display_name="Old Name",
            auth_provider="email",
        )
        db_session.add(existing)
        await db_session.commit()
        await db_session.refresh(existing)

        repo = UserRepository(db_session)

        user = await repo.find_or_create_by_auth_uid(
            auth_uid="fb-uid-name-change",
            email="user@example.com",
            display_name="New Name",
            auth_provider="email",
        )

        assert user.display_name == "New Name"

    @pytest.mark.unit
    async def test_updates_auth_provider_when_changed(self, db_session: AsyncSession):
        existing = User(
            auth_uid="fb-uid-provider-change",
            email="user@example.com",
            display_name="User",
            auth_provider="email",
        )
        db_session.add(existing)
        await db_session.commit()
        await db_session.refresh(existing)

        repo = UserRepository(db_session)

        user = await repo.find_or_create_by_auth_uid(
            auth_uid="fb-uid-provider-change",
            email="user@example.com",
            display_name="User",
            auth_provider="google",
        )

        assert user.auth_provider == "google"

    @pytest.mark.unit
    async def test_no_commit_when_nothing_changed(self, db_session: AsyncSession):
        existing = User(
            auth_uid="fb-uid-no-change",
            email="same@example.com",
            display_name="Same Name",
            auth_provider="email",
        )
        db_session.add(existing)
        await db_session.commit()
        await db_session.refresh(existing)

        repo = UserRepository(db_session)

        user = await repo.find_or_create_by_auth_uid(
            auth_uid="fb-uid-no-change",
            email="same@example.com",
            display_name="Same Name",
            auth_provider="email",
        )

        assert user.id == existing.id

    @pytest.mark.unit
    async def test_creates_user_with_none_email(self, db_session: AsyncSession):
        repo = UserRepository(db_session)

        user = await repo.find_or_create_by_auth_uid(
            auth_uid="fb-uid-no-email",
            email=None,
            display_name=None,
            auth_provider="apple",
        )

        assert user.auth_uid == "fb-uid-no-email"
        assert user.email is None
        assert user.display_name is None


