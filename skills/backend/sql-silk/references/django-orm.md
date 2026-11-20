# Django ORM

In Django the ORM is the data layer, so there is no `db_service.py`. Helpers (`apps/<domain>/helpers.py`) query models directly. Project structure is in `django-spider`; this file covers database behaviour.

## Connections

- Django opens one connection per request/thread and closes it at the end unless `CONN_MAX_AGE` keeps it for reuse (`CONN_MAX_AGE=60` and `CONN_HEALTH_CHECKS=True` for PostgreSQL in production).
- Database settings come from `.env` (`DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`), SQLite only as the local fallback.
- With `ATOMIC_REQUESTS` off (the default), each query autocommits; use `transaction.atomic()` for groups of writes.

## Transactions

```python
class TicketHelper:
    """Business rules for tickets."""

    @classmethod
    @transaction.atomic
    def change_status(cls, ticket_id: int, user, new_status: str) -> Ticket:
        """Move a ticket to a new status and record the change."""
        ticket = Ticket.objects.select_for_update().filter(id=ticket_id).first()
        ...
        TicketHistory.objects.create(ticket=ticket, action=..., changed_by=user)
        return ticket
```

- Several writes that belong together (ticket update + history row) run in one `transaction.atomic` block.
- `select_for_update()` on rows that are read and then changed, to stop two requests overwriting each other.
- Never keep an atomic block open across slow work (email sending, LLM, external API). Do the slow work after the block, or use `transaction.on_commit(...)` to send email only once the data is saved.

## Queries

- Scope every queryset by the current user or role first (`Ticket.objects.filter(customer=user)`), in one helper method such as `get_tickets_for_user(user)` that every view reuses.
- `select_related` for foreign keys and `prefetch_related` for reverse/many relations used by serializers, to avoid N+1.
- Search with `Q(title__icontains=term) | Q(description__icontains=term)`; filters from query params; DRF `PageNumberPagination` for pages.
- `.exists()` for existence checks, `.only()` / `.values()` for large lists that need few fields.
- `get_object_or_404` only after scoping (`get_object_or_404(scoped_queryset, pk=pk)`), so other users' records return 404.

## Models

- `created_at = models.DateTimeField(auto_now_add=True)`, `updated_at = models.DateTimeField(auto_now=True)`.
- `TextChoices` for status/role fields; `Meta.ordering` with a unique tiebreaker; `Meta.indexes` for filtered fields; `UniqueConstraint` with a `name`.
- `on_delete=PROTECT` for owners whose history must survive, `CASCADE` for true children, `SET_NULL` for audit references.
- Custom `User` model before the first migration.

## Migrations

`python manage.py makemigrations <app>` → read the file → `python manage.py migrate` → commit with the model change. `sqlmigrate <app> <number>` shows the SQL. The same rules as Alembic apply: never edit applied migrations, backfill before NOT NULL (Django asks for a one-off default; prefer a data migration with `RunPython` for real backfills).

## Errors

- `IntegrityError` on a unique field → 409 in the helper (or a `UniqueValidator` in the serializer).
- `OperationalError` / `InterfaceError` (database down) → 424 in the project's custom DRF exception handler.
