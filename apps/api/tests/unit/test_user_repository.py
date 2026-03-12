"""Unit tests for UserRepository auth-related methods."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from coyo.models.user import AuthProvider, User
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
            auth_provider=AuthProvider.EMAIL,
        )

        assert user.id is not None
        assert user.auth_uid == "fb-new-uid"
        assert user.email == "new@example.com"
        assert user.display_name == "New User"
        assert user.auth_provider == AuthProvider.EMAIL

    @pytest.mark.unit
    async def test_returns_existing_user_when_found(self, db_session: AsyncSession):
        # Arrange: create a user with a auth_uid
        existing = User(
            auth_uid="fb-existing-uid",
            email="existing@example.com",
            display_name="Existing User",
            auth_provider=AuthProvider.GOOGLE,
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
            auth_provider=AuthProvider.GOOGLE,
        )

        assert user.id == existing.id

    @pytest.mark.unit
    async def test_updates_email_when_changed(self, db_session: AsyncSession):
        existing = User(
            auth_uid="fb-uid-email-change",
            email="old@example.com",
            display_name="User",
            auth_provider=AuthProvider.EMAIL,
        )
        db_session.add(existing)
        await db_session.commit()
        await db_session.refresh(existing)

        repo = UserRepository(db_session)

        user = await repo.find_or_create_by_auth_uid(
            auth_uid="fb-uid-email-change",
            email="new@example.com",
            display_name="User",
            auth_provider=AuthProvider.EMAIL,
        )

        assert user.id == existing.id
        assert user.email == "new@example.com"

    @pytest.mark.unit
    async def test_updates_display_name_when_changed(self, db_session: AsyncSession):
        existing = User(
            auth_uid="fb-uid-name-change",
            email="user@example.com",
            display_name="Old Name",
            auth_provider=AuthProvider.EMAIL,
        )
        db_session.add(existing)
        await db_session.commit()
        await db_session.refresh(existing)

        repo = UserRepository(db_session)

        user = await repo.find_or_create_by_auth_uid(
            auth_uid="fb-uid-name-change",
            email="user@example.com",
            display_name="New Name",
            auth_provider=AuthProvider.EMAIL,
        )

        assert user.display_name == "New Name"

    @pytest.mark.unit
    async def test_updates_auth_provider_when_changed(self, db_session: AsyncSession):
        existing = User(
            auth_uid="fb-uid-provider-change",
            email="user@example.com",
            display_name="User",
            auth_provider=AuthProvider.EMAIL,
        )
        db_session.add(existing)
        await db_session.commit()
        await db_session.refresh(existing)

        repo = UserRepository(db_session)

        user = await repo.find_or_create_by_auth_uid(
            auth_uid="fb-uid-provider-change",
            email="user@example.com",
            display_name="User",
            auth_provider=AuthProvider.GOOGLE,
        )

        assert user.auth_provider == AuthProvider.GOOGLE

    @pytest.mark.unit
    async def test_no_commit_when_nothing_changed(self, db_session: AsyncSession):
        existing = User(
            auth_uid="fb-uid-no-change",
            email="same@example.com",
            display_name="Same Name",
            auth_provider=AuthProvider.EMAIL,
        )
        db_session.add(existing)
        await db_session.commit()
        await db_session.refresh(existing)

        repo = UserRepository(db_session)

        user = await repo.find_or_create_by_auth_uid(
            auth_uid="fb-uid-no-change",
            email="same@example.com",
            display_name="Same Name",
            auth_provider=AuthProvider.EMAIL,
        )

        assert user.id == existing.id

    @pytest.mark.unit
    async def test_creates_user_with_none_email(self, db_session: AsyncSession):
        repo = UserRepository(db_session)

        user = await repo.find_or_create_by_auth_uid(
            auth_uid="fb-uid-no-email",
            email=None,
            display_name=None,
            auth_provider=AuthProvider.APPLE,
        )

        assert user.auth_uid == "fb-uid-no-email"
        assert user.email is None
        assert user.display_name is None

    @pytest.mark.unit
    async def test_updates_multiple_fields_at_once(self, db_session: AsyncSession):
        """When email, display_name, and auth_provider all differ, all are updated."""
        existing = User(
            auth_uid="fb-uid-multi-update",
            email="old@example.com",
            display_name="Old Name",
            auth_provider=AuthProvider.EMAIL,
        )
        db_session.add(existing)
        await db_session.commit()
        await db_session.refresh(existing)

        repo = UserRepository(db_session)

        user = await repo.find_or_create_by_auth_uid(
            auth_uid="fb-uid-multi-update",
            email="new@example.com",
            display_name="New Name",
            auth_provider=AuthProvider.GOOGLE,
        )

        assert user.id == existing.id
        assert user.email == "new@example.com"
        assert user.display_name == "New Name"
        assert user.auth_provider == AuthProvider.GOOGLE


class TestFindOrCreateRaceCondition:
    """Tests for the IntegrityError race condition retry path."""

    @pytest.mark.unit
    async def test_integrity_error_retries_and_finds_user(
        self, db_session: AsyncSession
    ):
        """Simulate concurrent insert: commit raises IntegrityError, retry finds user."""
        # Pre-insert the user that the "other process" created
        existing = User(
            auth_uid="fb-race-uid",
            email="race@example.com",
            display_name="Race User",
            auth_provider=AuthProvider.EMAIL,
        )
        db_session.add(existing)
        await db_session.commit()
        await db_session.refresh(existing)

        repo = UserRepository(db_session)

        with (
            patch.object(
                repo,
                "find_by_auth_uid",
                new_callable=AsyncMock,
                side_effect=[None, existing],
            ),
            patch.object(
                db_session,
                "commit",
                side_effect=IntegrityError(
                    statement="INSERT",
                    params={},
                    orig=Exception("UNIQUE constraint failed"),
                ),
            ),
            patch.object(db_session, "rollback", new_callable=AsyncMock),
            patch.object(db_session, "add"),
        ):
            user = await repo.find_or_create_by_auth_uid(
                auth_uid="fb-race-uid",
                email="race@example.com",
                display_name="Race User",
                auth_provider=AuthProvider.EMAIL,
            )

        assert user.id == existing.id
        assert user.auth_uid == "fb-race-uid"

    @pytest.mark.unit
    async def test_integrity_error_reraises_when_retry_returns_none(
        self, db_session: AsyncSession
    ):
        """IntegrityError is re-raised if the retry find also returns None."""
        repo = UserRepository(db_session)

        async def mock_find(auth_uid: str) -> User | None:
            return None  # Both first and retry calls return None

        async def mock_commit() -> None:
            raise IntegrityError(
                statement="INSERT",
                params={},
                orig=Exception("UNIQUE constraint failed"),
            )

        with (
            patch.object(repo, "find_by_auth_uid", side_effect=mock_find),
            patch.object(db_session, "commit", side_effect=mock_commit),
            patch.object(db_session, "rollback", new_callable=AsyncMock),
            patch.object(db_session, "add"),
            pytest.raises(IntegrityError),
        ):
            await repo.find_or_create_by_auth_uid(
                auth_uid="fb-nonexistent-uid",
                email="ghost@example.com",
                display_name="Ghost",
                auth_provider=AuthProvider.EMAIL,
            )
