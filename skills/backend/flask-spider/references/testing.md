# Testing

Tests cover critical paths. What to cover is the same as for FastAPI (`fastapi-spider/references/testing.md`: auth, ownership, validation, updates, lists, failures); only the setup differs.

## conftest.py

```python
import os

import pytest

os.environ.update(DATABASE_URL="sqlite:///" + os.path.abspath("test.db"), JWT_SECRET_KEY="test-secret-key-with-at-least-32-chars", LOG_LEVEL="WARNING")

from app import create_app  # noqa: E402  (env must be set before the app is imported)
from app.extensions import db  # noqa: E402


@pytest.fixture
def app():
    """Application with a clean test database."""
    flask_app = create_app()
    with flask_app.app_context():
        db.drop_all()
        db.create_all()
    yield flask_app


@pytest.fixture
def client(app):
    """Test client; the app context lets DBService reach db.engine."""
    with app.test_client() as test_client, app.app_context():
        yield test_client


@pytest.fixture
def auth_headers(client):
    """Register and log in a user, return its Authorization header."""
    credentials = {"email": "owner@example.com", "password": "Str0ng!Pass"}
    client.post("/api/v1/auth/register", json=credentials)
    token = client.post("/api/v1/auth/login", json=credentials).get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

- Leave `TESTING` off so error handlers run as in production (with `TESTING=True` and `PROPAGATE_EXCEPTIONS`, unexpected exceptions are raised into the test instead of becoming 500 responses).
- `db.create_all()` is only for the throwaway test database; real databases use migrations.
- Responses: `response.get_json()`, `response.status_code`, `response.headers`.

## Mocking

- Database down: `monkeypatch.setattr(DBService, "new_session", raising_function)` where the function raises `sqlalchemy.exc.OperationalError` → expect 424.
- External services: patch the service class the helper calls; never call real paid APIs.

## Running

```bat
venv\Scripts\activate
pytest -q
```
