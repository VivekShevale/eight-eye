# Logging

## Setup (once per project)

1. Copy `assets/log_utils.py` to `app/utils/log_utils.py`.
2. Put `LOG_LEVEL` and `LOG_TO_FILE` in `.env` and `.env.example`; read them once in `config.py` (`settings.log_level`, `settings.log_to_file`).
3. Call `LogUtils.configure_logging()` once, first thing at startup: top of `main.py` (FastAPI, before creating the app), start of `create_app()` (Flask), FastMCP `main.py`. Django uses the `LOGGING` dict in settings instead (see `django-spider`), with the same format and env flags.
4. Every other module only declares, at the top after imports:

```python
logger = LogUtils.get_logger(__name__)
```

Nothing else calls `logging.basicConfig`, adds handlers or reads `LOG_LEVEL`.

Framework notes for `SERVER_LOGGERS` in `LogUtils`: FastAPI/FastMCP route `uvicorn`, `uvicorn.error`, `uvicorn.access`; Flask routes `werkzeug` and clears `app.logger.handlers` after setup so Flask logs go through the root logger.

`LOG_TO_FILE=true` writes `logs/app.log`, rotating at 5 MB with 5 backups. `logs/` is gitignored. A restart is needed after changing `.env`.

## Levels

| Level | Use for | Example |
|---|---|---|
| DEBUG | Reads and diagnostics | `Expenses listed \| user_id=%s \| count=%s` |
| INFO | Business events and completed processing | `Expense created \| expense_id=%s \| user_id=%s` |
| WARNING | Rejected requests, 4xx, recoverable problems | `Login rejected \| reason=invalid_credentials` |
| ERROR | Failures, via `logger.exception` to include the traceback | `Database operation failed \| error_type=%s` |
| CRITICAL | The app cannot work at all | `Required secret missing at startup` |

## What to log

- Business events: create, update, delete, login success, registration
- Rejected requests (WARNING, no traceback)
- Dependency failures (DB, vector store, LLM, other repos) with `error_type`
- Outbound calls and slow work with `duration_ms` (LLM calls also with input/output tokens)
- Document processing results (pages, chunks), background tasks

Where: in helpers, services and `ErrorHandlers`. Not in routes, models or schemas.

## Never log

Passwords, tokens, API keys, `Authorization` headers, connection strings, full request bodies, email addresses or other personal data, document or email contents. Log ids instead (`user_id`, `document_id`).

## Format

- Line format: `%(asctime)s | %(levelname)s | %(name)s | %(message)s`
- Message: an event name, then `| key=value` pairs: `"PDF processed | document_id=%s | pages=%s | chunks=%s"`
- Use `%s` placeholders, not f-strings, and keep placeholder count equal to argument count (a mismatch raises a logging error at runtime).
- Log each failure once, at the layer that handles it (see `errors-and-edge-cases.md`).
