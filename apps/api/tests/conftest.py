"""Shared test fixtures for the Coyo API test suite.

Provides an async in-memory SQLite database, a FastAPI TestClient,
mock dependencies, and reusable data fixtures.
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from coyo.models.base import Base
from coyo.models.conversation import Conversation
from coyo.models.correction import CorrectionItem, TurnCorrection
from coyo.models.turn import Turn
from coyo.models.user import User

# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///"


@pytest.fixture
async def engine():
    """Create an async in-memory SQLite engine for testing."""
    test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # SQLite requires the connection to enable foreign keys
    @event.listens_for(test_engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield test_engine

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


@pytest.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session with automatic rollback."""
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Application fixtures
# ---------------------------------------------------------------------------

DEVICE_ID = "00000000-0000-4000-a000-000000000001"


@pytest.fixture
def device_id() -> str:
    """Return a fixed test device ID."""
    return DEVICE_ID


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create and persist a test user."""
    user = User(device_id=DEVICE_ID)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_conversation(
    db_session: AsyncSession,
    test_user: User,
) -> Conversation:
    """Create and persist a test conversation with 'active' status."""
    conversation = Conversation(
        user_id=test_user.id,
        topic="technology",
        status="active",
        time_limit_seconds=1800,
        started_at=datetime.now(UTC),
    )
    db_session.add(conversation)
    await db_session.commit()
    await db_session.refresh(conversation)
    return conversation


@pytest.fixture
async def completed_conversation(
    db_session: AsyncSession,
    test_user: User,
) -> Conversation:
    """Create and persist a test conversation with 'completed' status."""
    started = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    ended = datetime(2025, 1, 1, 12, 15, 0, tzinfo=UTC)
    conversation = Conversation(
        user_id=test_user.id,
        topic="sports",
        status="completed",
        time_limit_seconds=1800,
        started_at=started,
        ended_at=ended,
        duration_seconds=900,
        total_corrections=2,
    )
    db_session.add(conversation)
    await db_session.commit()
    await db_session.refresh(conversation)
    return conversation


@pytest.fixture
async def paused_conversation(
    db_session: AsyncSession,
    test_user: User,
) -> Conversation:
    """Create and persist a test conversation with 'paused' status."""
    conversation = Conversation(
        user_id=test_user.id,
        topic="business",
        status="paused",
        time_limit_seconds=1800,
        started_at=datetime.now(UTC),
    )
    db_session.add(conversation)
    await db_session.commit()
    await db_session.refresh(conversation)
    return conversation


@pytest.fixture
async def test_turn(
    db_session: AsyncSession,
    test_conversation: Conversation,
) -> Turn:
    """Create and persist a user turn for the test conversation."""
    turn = Turn(
        conversation_id=test_conversation.id,
        role="user",
        text="I goed to the store yesterday.",
        sequence=1,
        correction_status="pending",
    )
    db_session.add(turn)
    await db_session.commit()
    await db_session.refresh(turn)
    return turn


@pytest.fixture
async def test_ai_turn(
    db_session: AsyncSession,
    test_conversation: Conversation,
) -> Turn:
    """Create and persist an AI turn for the test conversation."""
    turn = Turn(
        conversation_id=test_conversation.id,
        role="ai",
        text="That sounds great! What did you buy?",
        sequence=2,
        correction_status="none",
    )
    db_session.add(turn)
    await db_session.commit()
    await db_session.refresh(turn)
    return turn


@pytest.fixture
async def test_correction(
    db_session: AsyncSession,
    test_turn: Turn,
    test_user: User,
) -> TurnCorrection:
    """Create and persist a TurnCorrection with items for the test turn."""
    correction = TurnCorrection(
        turn_id=test_turn.id,
        corrected_text="I went to the store yesterday.",
        explanation="Past tense of 'go' is 'went', not 'goed'.",
    )
    db_session.add(correction)
    await db_session.flush()

    item = CorrectionItem(
        turn_correction_id=correction.id,
        user_id=test_user.id,
        original="goed",
        corrected="went",
        original_sentence="I goed to the store yesterday.",
        corrected_sentence="I went to the store yesterday.",
        type="grammar",
        explanation="'go' is an irregular verb; its past tense is 'went'.",
    )
    db_session.add(item)

    # Update turn correction_status
    test_turn.correction_status = "has_corrections"
    await db_session.commit()
    await db_session.refresh(correction)
    return correction


# ---------------------------------------------------------------------------
# Settings mock
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock get_settings to avoid needing real environment variables."""
    mock = MagicMock()
    mock.environment = "development"
    mock.debug = False
    mock.database_url = TEST_DATABASE_URL
    mock.redis_url = "redis://localhost:6379"
    mock.openai_api_key = "test-api-key"
    mock.llm_conversation_model = "gpt-5-mini"
    mock.llm_correction_model = "gpt-5-mini"
    mock.tts_voice = "nova"
    mock.tts_model = "tts-1"
    mock.gcs_bucket_name = "test-bucket"
    mock.gcs_audio_ttl_seconds = 3600
    mock.cors_allowed_origins = ["http://localhost:8081"]
    mock.max_audio_size_bytes = 10 * 1024 * 1024
    mock.rate_limit_per_minute = 30

    with patch("coyo.config.get_settings", return_value=mock):
        yield mock


# ---------------------------------------------------------------------------
# FastAPI TestClient fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def client(
    db_session: AsyncSession,
    test_user: User,
) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client with overridden dependencies.

    Overrides get_db to use the test session and get_current_user to
    return the test user, bypassing the X-Device-Id header requirement.
    """
    from coyo.dependencies import get_current_user, get_db
    from coyo.main import app

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# OpenAI mock fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_openai_client():
    """Create a mock AsyncOpenAI client for STT, TTS, and LLM tests."""
    mock_client = AsyncMock()

    # STT transcription mock
    transcription_mock = MagicMock()
    transcription_mock.text = "I went to the store yesterday."
    mock_client.audio.transcriptions.create = AsyncMock(return_value=transcription_mock)

    # TTS speech mock
    tts_response = MagicMock()
    tts_response.content = b"fake-audio-bytes"
    mock_client.audio.speech.create = AsyncMock(return_value=tts_response)

    # Chat completions mock (non-streaming)
    completion_message = MagicMock()
    completion_message.content = '{"has_errors": false, "corrected_text": "test", "explanation": "", "items": []}'
    completion_choice = MagicMock()
    completion_choice.message = completion_message
    completion_response = MagicMock()
    completion_response.choices = [completion_choice]
    mock_client.chat.completions.create = AsyncMock(return_value=completion_response)

    return mock_client
