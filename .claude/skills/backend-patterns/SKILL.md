---
name: backend-patterns
description: Backend architecture patterns, API design, database optimization, and server-side best practices for Python, FastAPI, and SQLAlchemy.
---

# Backend Development Patterns

Backend architecture patterns and best practices for scalable Python server-side applications.

## API Design Patterns

### RESTful API Structure

```
# ✅ Resource-based URLs
GET    /api/markets                 # List resources
GET    /api/markets/:id             # Get single resource
POST   /api/markets                 # Create resource
PUT    /api/markets/:id             # Replace resource
PATCH  /api/markets/:id             # Update resource
DELETE /api/markets/:id             # Delete resource

# ✅ Query parameters for filtering, sorting, pagination
GET /api/markets?status=active&sort=volume&limit=20&offset=0
```

### Repository Pattern

```python
from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


# Abstract data access logic
class MarketRepository(ABC):
    @abstractmethod
    async def find_all(self, filters: MarketFilters | None = None) -> list[Market]: ...

    @abstractmethod
    async def find_by_id(self, market_id: str) -> Market | None: ...

    @abstractmethod
    async def create(self, data: CreateMarketDto) -> Market: ...

    @abstractmethod
    async def update(self, market_id: str, data: UpdateMarketDto) -> Market: ...

    @abstractmethod
    async def delete(self, market_id: str) -> None: ...


class SQLAlchemyMarketRepository(MarketRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_all(self, filters: MarketFilters | None = None) -> list[Market]:
        stmt = select(MarketModel)

        if filters and filters.status:
            stmt = stmt.where(MarketModel.status == filters.status)

        if filters and filters.limit:
            stmt = stmt.limit(filters.limit)

        result = await self._session.execute(stmt)
        return [Market.model_validate(row) for row in result.scalars().all()]

    # Other methods...
```

### Service Layer Pattern

```python
# Business logic separated from data access
class MarketService:
    def __init__(self, market_repo: MarketRepository) -> None:
        self._market_repo = market_repo

    async def search_markets(self, query: str, limit: int = 10) -> list[Market]:
        # Business logic
        embedding = await generate_embedding(query)
        results = await self._vector_search(embedding, limit)

        # Fetch full data
        ids = [r.id for r in results]
        markets = await self._market_repo.find_by_ids(ids)

        # Sort by similarity
        score_map = {r.id: r.score for r in results}
        markets.sort(key=lambda m: score_map.get(m.id, 0))
        return markets

    async def _vector_search(
        self, embedding: list[float], limit: int
    ) -> list[VectorResult]:
        # Vector search implementation
        ...
```

### Middleware Pattern

```python
from fastapi import Depends, Header, HTTPException


# FastAPI dependency injection for request processing pipeline
async def get_current_user(
    authorization: str = Header(...),
) -> User:
    token = authorization.replace("Bearer ", "")

    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        return verify_token(token)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# Usage
@router.get("/me")
async def get_profile(user: User = Depends(get_current_user)) -> UserResponse:
    # Handler has access to user via dependency injection
    ...
```

## Database Patterns

### Query Optimization

```python
from sqlalchemy import select

# ✅ GOOD: Select only needed columns
stmt = (
    select(MarketModel.id, MarketModel.name, MarketModel.status, MarketModel.volume)
    .where(MarketModel.status == "active")
    .order_by(MarketModel.volume.desc())
    .limit(10)
)

# ❌ BAD: Select everything
stmt = select(MarketModel)
```

### N+1 Query Prevention

```python
from sqlalchemy.orm import selectinload

# ❌ BAD: N+1 query problem
markets = (await session.execute(select(MarketModel))).scalars().all()
for market in markets:
    creator = await session.execute(
        select(UserModel).where(UserModel.id == market.creator_id)
    )  # N queries

# ✅ GOOD: Eager loading with selectinload
stmt = select(MarketModel).options(selectinload(MarketModel.creator))
result = await session.execute(stmt)
markets = result.scalars().all()  # 2 queries total

# ✅ GOOD: Batch fetch with IN clause
markets = (await session.execute(select(MarketModel))).scalars().all()
creator_ids = [m.creator_id for m in markets]
creators = (
    await session.execute(select(UserModel).where(UserModel.id.in_(creator_ids)))
).scalars().all()
creator_map = {c.id: c for c in creators}

for market in markets:
    market.creator = creator_map.get(market.creator_id)
```

### Transaction Pattern

```python
from sqlalchemy.ext.asyncio import AsyncSession


async def create_market_with_position(
    session: AsyncSession,
    market_data: CreateMarketDto,
    position_data: CreatePositionDto,
) -> Market:
    async with session.begin():
        market = MarketModel(**market_data.model_dump())
        session.add(market)
        await session.flush()  # Get market.id before commit

        position = PositionModel(
            market_id=market.id,
            **position_data.model_dump(),
        )
        session.add(position)
    # Transaction committed automatically on exiting the context manager
    # Rollback happens automatically on exception

    await session.refresh(market)
    return Market.model_validate(market)
```

## Caching Strategies

### Redis Caching Layer

```python
from redis.asyncio import Redis


class CachedMarketRepository(MarketRepository):
    def __init__(self, base_repo: MarketRepository, redis: Redis) -> None:
        self._base_repo = base_repo
        self._redis = redis

    async def find_by_id(self, market_id: str) -> Market | None:
        cache_key = f"market:{market_id}"

        # Check cache first
        cached = await self._redis.get(cache_key)
        if cached:
            return Market.model_validate_json(cached)

        # Cache miss - fetch from database
        market = await self._base_repo.find_by_id(market_id)

        if market:
            # Cache for 5 minutes
            await self._redis.setex(cache_key, 300, market.model_dump_json())

        return market

    async def invalidate_cache(self, market_id: str) -> None:
        await self._redis.delete(f"market:{market_id}")
```

### Cache-Aside Pattern

```python
async def get_market_with_cache(market_id: str) -> Market:
    cache_key = f"market:{market_id}"

    # Try cache
    cached = await redis.get(cache_key)
    if cached:
        return Market.model_validate_json(cached)

    # Cache miss - fetch from DB
    market = await repo.find_by_id(market_id)

    if not market:
        raise ValueError("Market not found")

    # Update cache
    await redis.setex(cache_key, 300, market.model_dump_json())

    return market
```

## Error Handling Patterns

### Centralized Exception Handler

```python
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError


class ApiError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)


app = FastAPI()


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.message},
    )


@app.exception_handler(ValidationError)
async def validation_error_handler(
    request: Request, exc: ValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "error": "Validation failed",
            "details": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logging.exception("Unexpected error")
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error"},
    )
```

### Retry with Exponential Backoff

```python
import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def fetch_with_retry(
    fn: Callable[[], Awaitable[T]],
    max_retries: int = 3,
) -> T:
    last_error: Exception | None = None

    for i in range(max_retries):
        try:
            return await fn()
        except Exception as e:
            last_error = e
            if i < max_retries - 1:
                # Exponential backoff: 1s, 2s, 4s
                await asyncio.sleep(2**i)

    raise last_error  # type: ignore[misc]


# Usage
data = await fetch_with_retry(fetch_from_api)

# Or use tenacity (recommended for production)
from tenacity import retry, stop_after_attempt, wait_exponential


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def fetch_from_api() -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        response.raise_for_status()
        return response.json()
```

## Authentication & Authorization

### JWT Token Validation

```python
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

security = HTTPBearer()


class JWTPayload(BaseModel):
    user_id: str
    email: str
    role: str


def verify_token(token: str) -> JWTPayload:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return JWTPayload(**payload)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> JWTPayload:
    return verify_token(credentials.credentials)


# Usage in API route
@router.get("/me")
async def get_profile(user: JWTPayload = Depends(get_current_user)) -> UserResponse:
    data = await get_data_for_user(user.user_id)
    return UserResponse.model_validate(data)
```

### Role-Based Access Control

```python
from enum import StrEnum

from fastapi import Depends, HTTPException


class Permission(StrEnum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"


class Role(StrEnum):
    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.ADMIN: {Permission.READ, Permission.WRITE, Permission.DELETE, Permission.ADMIN},
    Role.MODERATOR: {Permission.READ, Permission.WRITE, Permission.DELETE},
    Role.USER: {Permission.READ, Permission.WRITE},
}


def has_permission(user: JWTPayload, permission: Permission) -> bool:
    role = Role(user.role)
    return permission in ROLE_PERMISSIONS.get(role, set())


def require_permission(permission: Permission):
    """FastAPI dependency that checks user permissions."""
    async def _check(user: JWTPayload = Depends(get_current_user)) -> JWTPayload:
        if not has_permission(user, permission):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return _check


# Usage - dependency injection handles auth + permission check
@router.delete("/{market_id}")
async def delete_market(
    market_id: str,
    user: JWTPayload = Depends(require_permission(Permission.DELETE)),
) -> dict:
    # Handler receives authenticated user with verified permission
    await service.delete(market_id)
    return {"success": True}
```

## Rate Limiting

### Simple In-Memory Rate Limiter

```python
import time
from collections import defaultdict

from fastapi import Depends, HTTPException, Request


class RateLimiter:
    def __init__(self) -> None:
        self._requests: dict[str, list[float]] = defaultdict(list)

    def check_limit(
        self, identifier: str, max_requests: int, window_seconds: float
    ) -> bool:
        now = time.monotonic()
        requests = self._requests[identifier]

        # Remove old requests outside window
        self._requests[identifier] = [
            t for t in requests if now - t < window_seconds
        ]

        if len(self._requests[identifier]) >= max_requests:
            return False  # Rate limit exceeded

        # Add current request
        self._requests[identifier].append(now)
        return True


limiter = RateLimiter()


async def rate_limit_dependency(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    if not limiter.check_limit(client_ip, max_requests=100, window_seconds=60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


@router.get("/", dependencies=[Depends(rate_limit_dependency)])
async def list_markets() -> list[MarketResponse]:
    # Continue with request
    ...
```

## Background Jobs & Queues

### asyncio Task Queue

```python
import asyncio
import logging
from dataclasses import dataclass


@dataclass
class IndexJob:
    market_id: str


class JobQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[IndexJob] = asyncio.Queue()
        self._running = False

    async def add(self, job: IndexJob) -> None:
        await self._queue.put(job)
        if not self._running:
            asyncio.create_task(self._process())

    async def _process(self) -> None:
        self._running = True
        while not self._queue.empty():
            job = await self._queue.get()
            try:
                await self._execute(job)
            except Exception:
                logging.exception("Job failed: %s", job)
            finally:
                self._queue.task_done()
        self._running = False

    async def _execute(self, job: IndexJob) -> None:
        # Job execution logic
        ...


# Usage for indexing markets
index_queue = JobQueue()


@router.post("/index")
async def queue_index(market_id: str) -> dict:
    # Add to queue instead of blocking
    await index_queue.add(IndexJob(market_id=market_id))
    return {"success": True, "message": "Job queued"}
```

### Celery Task (Production)

```python
from celery import Celery

celery_app = Celery("worker", broker="redis://localhost:6379/0")


@celery_app.task(bind=True, max_retries=3)
def index_market_task(self, market_id: str) -> dict:
    try:
        result = index_market(market_id)
        return {"success": True, "market_id": market_id}
    except Exception as exc:
        self.retry(exc=exc, countdown=2**self.request.retries)


@router.post("/index")
async def queue_index(market_id: str) -> dict:
    index_market_task.delay(market_id)
    return {"success": True, "message": "Job queued"}
```

## Logging & Monitoring

### Structured Logging

```python
import uuid

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),  # Use JSONRenderer in production
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        logger.info("Request started")

        try:
            response = await call_next(request)
            logger.info("Request completed", status_code=response.status_code)
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            logger.exception("Request failed")
            raise


# Usage in routes
@router.get("/")
async def list_markets() -> list[MarketResponse]:
    logger.info("Fetching markets")
    try:
        markets = await fetch_markets()
        return [MarketResponse.model_validate(m) for m in markets]
    except Exception:
        logger.exception("Failed to fetch markets")
        raise
```

**Remember**: Backend patterns enable scalable, maintainable server-side applications. Choose patterns that fit your complexity level.
