# Apps and Layers

## Contents
1. Deciding apps
2. Where code goes
3. View patterns
4. Serializer patterns
5. Helper patterns
6. Permissions and visibility
7. URLs
8. Common Django mistakes

## 1. Deciding apps

Ask: "Would this part of the system make sense and be explainable on its own?"

| Model | App |
|---|---|
| Ticket, TicketComment, TicketHistory, TicketAttachment | `tickets` |
| User, profile, password reset tokens, agent invitations | `accounts` |
| Invoice, Payment, Refund | `billing` |
| Product, StockMovement | `inventory` |

A model whose rows only exist for one parent (comments, attachments, history, line items) lives with that parent. Split an app later only when a domain clearly separates; merging apps after migrations exist is far harder than splitting a file.

## 2. Where code goes

| Code | Place |
|---|---|
| URL → view mapping | `apps/<domain>/urls.py` |
| Request handling (validate → helper → respond) | `views.py` |
| Input validation, output shape | `serializers.py` |
| Business rules, scoped querysets, transactions, history | `helpers.py` (`<Domain>Helper`) |
| Role checks | `permissions.py` (`BasePermission` classes) |
| Shared exception handler, pagination, health | `apps/common/` |
| Sending email, LLM, external APIs | `apps/<domain>/services.py` (a class per integration), called by helpers |
| Email templates | `apps/<domain>/templates/emails/` |

There is no `db_service.py` in Django: the ORM is the data layer (`sql-silk/references/django-orm.md`). A `utils.py` only appears for code shared by several apps, and it never calls helpers or touches the database.

## 3. View patterns

```python
class TicketStatusView(APIView):
    """PATCH: change a ticket's status along the allowed transitions."""

    def patch(self, request, pk: int):
        serializer = TicketStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = TicketHelper.change_status(pk, serializer.validated_data["status"], request.user)
        return Response(TicketSerializer(ticket).data)
```

- List endpoints: `generics.ListAPIView` with `get_queryset()` returning the helper's scoped queryset; the configured paginator returns `{"items", "page", "page_size", "total", "total_pages"}`.
- Create on the same URL as the list: add a `post` method to the list view; different permissions per method through `get_permissions()`.
- Detail: `generics.RetrieveAPIView` with the scoped `get_queryset()`; DRF returns 404 for ids outside it.
- Function-based views and `@api_view` are not used; keep one style.

## 4. Serializer patterns

- `XCreateSerializer` (`ModelSerializer` with only client-settable fields), `XSerializer` for output with related display fields (`customer_email = serializers.EmailField(source="customer.email", read_only=True)`), small `Serializer` classes for action payloads (`TicketStatusSerializer`, `TicketAssignSerializer`).
- Related ids from clients: `PrimaryKeyRelatedField(queryset=...)` restricted to valid choices (only active agents), so invalid ids are a 400.
- Serializers don't call helpers or write to the database; views pass `serializer.validated_data` to the helper.
- Output serializers used in lists need the related objects loaded: the helper's queryset uses `select_related` / `prefetch_related` (no N+1).

## 5. Helper patterns

```python
@classmethod
@transaction.atomic
def change_status(cls, ticket_id: int, new_status: str, changed_by: User) -> Ticket:
    """Move a ticket along the allowed transitions; customers may only cancel."""
    ticket = cls.get_ticket_for_user(changed_by, ticket_id, for_update=True)
    ...
```

- `get_<things>_for_user(user)` is the single entry point for every query on that model; list, detail, update and delete all go through it.
- `select_for_update(of=("self",))` when the scoped queryset joins other tables (nullable joins can't be locked on PostgreSQL).
- `save(update_fields=[...])` for partial updates, including `updated_at`.
- Log business events at INFO with ids only (`ticket_id=%s changed_by_id=%s`), rejected actions at WARNING.
- Email or notification after a write: `transaction.on_commit(lambda: EmailService.send_ticket_update(ticket.id))` style, or send after the atomic block, never inside it.

## 6. Permissions and visibility

| Question | Mechanism | Failure |
|---|---|---|
| Is the user logged in? | `IsAuthenticated` (default) | 401 |
| May this role do this action? | `IsCustomer`, `IsAdministrator` permission classes or a helper check | 403 |
| May this user see this record? | Scoped queryset | 404 |
| May this user change this specific record? (comment author) | Helper check after loading from the scoped queryset | 403 (the record is visible, the action isn't) |

## 7. URLs

```python
urlpatterns = [
    path("", TicketListCreateView.as_view(), name="ticket-list"),
    path("<int:pk>/", TicketDetailView.as_view(), name="ticket-detail"),
    path("<int:pk>/status/", TicketStatusView.as_view(), name="ticket-status"),
    path("<int:pk>/comments/", TicketCommentListCreateView.as_view(), name="ticket-comments"),
    path("<int:pk>/comments/<int:comment_id>/", TicketCommentDetailView.as_view(), name="ticket-comment-detail"),
]
```

Resource paths, not verb paths (`""` with POST instead of `create/`). Unique names per route.

## 8. Common Django mistakes

| Mistake | Fix |
|---|---|
| A new app for one model (`comments` next to `tickets`) | Put the model in its domain's app |
| Two views registered on the same path for PATCH and DELETE | One view with both methods |
| `AllowAny` on an endpoint that uses `request.user` | `IsAuthenticated` (default) |
| `SECRET_KEY = "django-insecure-..."` in settings | Required env var, no default |
| `db.sqlite3` committed | Gitignore it |
| Query params read with `request.query_params.get` and used unvalidated | Query-param serializer |
| Password policy duplicated in two serializers | One validator in one serializer (or a shared function) |
| Utilities that call helpers or delete records | That logic belongs in a helper |
| Packages in `requirements.txt` that aren't used (or used but missing, e.g. whitenoise) | Keep requirements equal to imports |
| `startapp` leftovers (`# Create your views here.`, empty `tests.py`) | Remove |
| Different error shapes (`{"detail"}`, `{"message"}`, field dicts) | Custom `EXCEPTION_HANDLER` |
