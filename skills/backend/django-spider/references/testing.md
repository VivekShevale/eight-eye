# Testing

Tests cover critical paths. Use Django's runner with DRF's `APITestCase`; no extra packages are needed. Each test runs in a transaction on a temporary test database that is created and destroyed automatically.

## Layout

`apps/<domain>/tests.py` for small apps, or `apps/<domain>/tests/test_<area>.py` (with `__init__.py`) when it grows. Replace the empty `tests.py` stub that `startapp` generates.

## Pattern

```python
class TicketTests(APITestCase):
    """Ticket visibility and actions."""

    def setUp(self):
        self.customer = User.objects.create_user("cust@example.com", "Str0ng!Pass")
        self.other = User.objects.create_user("other@example.com", "Str0ng!Pass")

    def auth(self, email: str) -> dict:
        """Log in through the API and return the Authorization header kwargs."""
        response = self.client.post("/api/v1/auth/login/", {"email": email, "password": "Str0ng!Pass"}, format="json")
        return {"HTTP_AUTHORIZATION": "Bearer " + response.json()["access"]}

    def test_other_users_ticket_is_not_found(self):
        ticket_id = self.client.post("/api/v1/tickets/", {"title": "t", "description": "d"}, format="json", **self.auth("cust@example.com")).json()["id"]
        response = self.client.get(f"/api/v1/tickets/{ticket_id}/", **self.auth("other@example.com"))
        self.assertEqual(response.status_code, 404)
```

`self.client.force_authenticate(user)` is a shortcut when the login flow itself isn't under test.

## What to cover

| Area | Cases |
|---|---|
| Auth | register 201, duplicate 409, weak password 400, wrong password and unknown email both 401 with the same message, no/invalid token 401, `role` sent at registration ignored |
| Visibility | other users' records 404 on detail, actions and nested resources; lists never include them |
| Roles | wrong role → 403 on role-restricted endpoints |
| Rules | invalid state transitions 400; history row written with each change |
| Validation | missing/invalid fields 400 with `details`; invalid query params 400 |
| Failures | `OperationalError` → 424, unexpected exception → 500 without internals (mock the helper with `unittest.mock.patch.object`) |

## Running

```bat
venv\Scripts\activate
python manage.py test
python manage.py test apps.tickets
```

Password hashing makes login-heavy tests slow; for large suites add `PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]` in a test-only settings module, never in the real settings.
