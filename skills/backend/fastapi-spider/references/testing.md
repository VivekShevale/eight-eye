# Testing

Tests cover critical paths. Evaluations of LLM behaviour are separate and exist only when requested (`rag-spider`, `mcp-spider`).

## Layout

```text
tests/
├── conftest.py          # env vars for a test database, client fixture, auth helpers
├── test_auth.py
├── test_expenses.py
└── test_failures.py     # dependency down, unexpected errors
```

`requirements-dev.txt`: `pytest`, plus `aiosqlite` if tests use SQLite.

## conftest.py

```python
import asyncio
import os

import pytest

os.environ.update(DATABASE_URL="sqlite+aiosqlite:///./test.db", JWT_SECRET_KEY="test-secret-key-with-at-least-32-chars", LOG_LEVEL="WARNING")

from fastapi.testclient import TestClient  # noqa: E402  (env must be set before the app is imported)

from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.services.db_service import DBService  # noqa: E402


async def reset_database() -> None:
    """Drop and create all tables in the test database."""
    async with DBService.engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)


@pytest.fixture
def client():
    """Test client with a clean database; the context manager runs the lifespan."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        asyncio.run(reset_database())
        yield test_client


@pytest.fixture
def auth_headers(client):
    """Register and log in a user, return its Authorization header."""
    credentials = {"email": "owner@example.com", "password": "Str0ng!Pass"}
    client.post("/api/v1/auth/register", json=credentials)
    token = client.post("/api/v1/auth/login", json=credentials).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

The env-before-import lines are the one place where imports follow code; they're needed so `config.py` reads the test settings. `create_all` is acceptable for a throwaway test database; real databases use migrations.

## What to cover

| Area | Cases |
|---|---|
| Auth | register 201, duplicate 409, weak password 422, wrong password and unknown email both 401 with the same message, no/invalid token 401 |
| Ownership | another user's record → 404 on get, patch and delete; lists never include other users' rows |
| Validation | extra fields 422, server-owned fields (`user_id`) rejected, bounds on page/page_size, reversed date range |
| Updates | empty PATCH 400, explicit null 400, only sent fields change |
| Lists | filters, search, pagination metadata, empty result 200 |
| Failures | DB not configured/unreachable → 424, unexpected exception → 500 with a generic message and no internals |
| External services | LLM/MCP/other repo mocked: success, timeout (504), unreachable (503), rate limit (429) |

## Mocking

- Patch the service the helper calls, not HTTP: `monkeypatch.setattr(LLMService, "generate_answer", fake_generate_answer)`.
- Simulate the database being down: `monkeypatch.setattr(DBService, "session_factory", None)` → expect 424.
- Never call real paid APIs in tests.

## Running

```bat
venv\Scripts\activate
pytest -q
```

Report the actual result (passed/failed counts); never claim tests pass without running them.
