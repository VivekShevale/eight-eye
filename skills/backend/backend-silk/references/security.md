# Security

## Passwords

- Strength policy with the `password-validator` library, applied at registration and password change only (never at login):

```python
PASSWORD_SCHEMA = PasswordValidator().min(8).max(72).has().uppercase().has().lowercase().has().digits().has().symbols().has().no().spaces()
```

  `max(72)` because bcrypt ignores bytes beyond 72; with werkzeug hashing 100 is fine.
- Hash with an established library: bcrypt (12 rounds) or werkzeug `generate_password_hash`. Never store, log or return plaintext.
- In async apps, run bcrypt in `asyncio.to_thread` so it doesn't block other requests.
- Registration order (fail fast): validate email → check duplicate (409) → check strength → hash → save. Keep the DB unique constraint as the guard against two simultaneous registrations.
- Login: one generic message, "Invalid email or password.", for unknown email and wrong password.

## JWT

- Library: PyJWT (FastAPI, FastMCP), Flask-JWT-Extended (Flask), SimpleJWT (Django).
- Secret from `.env`, at least 32 random characters: `python -c "import secrets; print(secrets.token_hex(32))"`.
- Claims: `sub` = user id as string, `iat`, `exp`; add `iss` and `aud` when more than one service accepts the token. Decode with `require=["sub", "exp", "iat"]` and the expected algorithm, issuer and audience.
- Short-lived access tokens (15–60 minutes, from config).
- The current user comes only from the verified token. Never accept `user_id`, `created_by` or `owner` from the request body.
- Logout with stateless JWT is client-side; add a token blacklist only if the requirement asks for server-side revocation.

## Ownership and roles

- Every read, update and delete query filters by the current user (`user_id == current_user_id`) or by role-scoped access.
- Another user's record returns 404, so its existence isn't leaked. 403 is only for "your role can't do this action".
- Audit fields (`created_by`, `updated_by`) are set from the token.
- Add roles only when the requirement has them.

## Secrets and config

- All secrets in `.env`; `.env` gitignored; `.env.example` committed with placeholders and comments on how to generate each secret.
- No default values for secrets in code (a hardcoded fallback secret ends up in production).
- Gitignore credential files: `credentials.json`, `token.json`, private keys (`*_private.pem`).
- If a secret appears in a chat, log or commit, tell the user to rotate it.

## Uploads

- Check extension and magic bytes (e.g. `%PDF-`), not only `content_type`.
- Enforce the size limit while reading (read `MAX + 1` bytes → 413).
- Store under a generated UUID name in a configured folder; never build paths from the client's filename.
- Delete the stored file if processing fails.

## Other

- CORS: explicit allowed origins from config; never `*` together with credentials.
- SQL: ORM or parameterized queries only; dynamic column names checked against an allow-list.
- LLM apps: treat retrieved documents and tool output as data, not instructions (state this in the system prompt).
- Rate-limit login and expensive endpoints when the app is publicly exposed (mention it; build it when asked).
- Prefer established libraries over custom security code.
