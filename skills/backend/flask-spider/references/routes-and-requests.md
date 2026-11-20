# Routes and Requests

## Contents
1. Blueprint template
2. Validating input
3. Responses and status codes
4. Errors from helpers
5. JWT details
6. CORS and uploads
7. Common Flask mistakes

## 1. Blueprint template

```python
expense_bp = Blueprint("expenses", __name__, url_prefix="/api/v1/expenses")


@expense_bp.get("")
@jwt_required()
def list_expenses():
    return ExpenseHelper.list_expenses(AuthUtils.get_current_user_id(), RequestUtils.parse_query(ExpenseListParams))
```

- The blueprint name (first argument) is unique per app; the variable is `<domain>_bp`.
- Method shortcuts (`.get`, `.post`, `.patch`, `.delete`) instead of `route(..., methods=[...])`.
- Register in `create_app()`: `app.register_blueprint(expense_bp)`.
- Child resources: `@chat_bp.post("/<chat_id>/messages")`.

## 2. Validating input

| Input | How |
|---|---|
| JSON body | `RequestUtils.parse_body(XCreateRequest)` (non-object or invalid JSON → 400) |
| Query string | `RequestUtils.parse_query(XListParams)`; values arrive as strings and Pydantic converts them |
| Path ids | URL converters `<int:id>`; string ids (UUID, ObjectId) validated in the helper (invalid → 404) |
| Current user | `AuthUtils.get_current_user_id()` inside `@jwt_required()` routes |

Schemas are the same as in FastAPI projects: `extra="forbid"`, `Field` constraints, optional update fields with `= None`, cross-field checks with `model_validator`, password policy with `password-validator`. `RequestValidationError` carries `[{"field": "body.email", "message": "..."}]`, and `ErrorHandlers` returns it as a 400 with `details`. A `pydantic.ValidationError` raised anywhere else is a server bug and becomes a 500.

## 3. Responses and status codes

- Helpers return `(dict, status)`. Build the dict from a response schema with `model_dump(mode="json")`, which turns `Decimal`, `date` and `datetime` into JSON-safe values.
- 201 create, 200 read/update, `("", 204)` delete.
- A route that returns a dependency value directly (like `/me` returning `AuthUtils.get_current_user()`) returns a plain dict with status 200.
- No `jsonify`; Flask serializes returned dicts.

## 4. Errors from helpers

| Situation | Raise |
|---|---|
| Missing or another user's record | `NotFound("Expense not found.")` |
| Duplicate | `Conflict("Email is already registered.")` |
| Bad input beyond the schema (empty PATCH, explicit null) | `BadRequest("...")` |
| Wrong credentials | `Unauthorized("Invalid email or password.")` |
| Role not allowed | `Forbidden("...")` |
| Upload too large | `RequestEntityTooLarge("...")` |

All from `werkzeug.exceptions`. Database outages and unexpected errors are left to `ErrorHandlers` (424 / 500); helpers don't catch them.

## 5. JWT details

- `create_access_token(identity=str(user.id))`: Flask-JWT-Extended requires a string identity.
- `JWT_ACCESS_TOKEN_EXPIRES` from `ACCESS_TOKEN_EXPIRE_MINUTES`; secret from `JWT_SECRET_KEY`.
- The user lookup loader runs one primary-key query per protected request, so deleted users can't keep using old tokens.
- Logout is client-side (discard the token) unless the requirement asks for server-side revocation (then a blocklist with `token_in_blocklist_loader`).

## 6. CORS and uploads

- `CORS(app, origins=settings.cors_origins, supports_credentials=True)` in `create_app()`; origins only from `.env`.
- Uploads: `request.files["file"]` is read in the route and passed to the helper as a `FileStorage`; the helper checks size (`MAX_CONTENT_LENGTH` in config gives Flask's own 413), extension and magic bytes, and stores under a UUID name (see `backend-silk/references/security.md`).

## 7. Common Flask mistakes

| Mistake | Fix |
|---|---|
| Error handlers defined with `@app.errorhandler` inside `create_app()` | Static methods on `ErrorHandlers`, registered with `app.register_error_handler` |
| FastAPI code copied into a Flask project (`from fastapi import ...` in `error_handlers.py`) | Use the Flask starter files |
| Helpers reading `request` directly | Routes pass validated schema objects |
| `@bp.get("/")` for collections | `@bp.get("")` |
| Models imported in `app/models/__init__.py` | Keep it empty; import models in `app/__init__.py` |
| `db.session` / `Model.query` in helpers | DBService |
| `total = len(items)` after paginating | Count the filtered query before offset/limit |
| Flask-JWT-Extended's default `{"msg": ...}` errors | Register the loaders from `ErrorHandlers` |
