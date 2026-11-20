# Querying

## Contents
1. Where queries live
2. A complete list endpoint
3. Search
4. Relationships and N+1
5. Aggregates, existence, bulk changes
6. Create and update from schemas

## 1. Where queries live

The helper builds `select()` statements; DBService executes them. Split a big list method into `parse_filter_parameters` (validate input) and `apply_<feature>_filters` (add `where` clauses), both methods of the helper class.

## 2. A complete list endpoint

```python
class ExpenseHelper:
    """Business logic for expenses."""

    MAX_PAGE_SIZE = 100

    @classmethod
    async def list_expenses(cls, user_id: int, filters: ExpenseListParams) -> ExpenseListResponse:
        """Return one page of the user's expenses with the applied filters."""
        statement = cls.apply_expense_filters(select(Expense).where(Expense.user_id == user_id), filters)
        count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
        total = await DBService.read(count_statement, one=True)
        page_statement = (
            statement.order_by(Expense.expense_date.desc(), Expense.id.desc())
            .offset((filters.page - 1) * filters.page_size)
            .limit(filters.page_size)
        )
        expenses = await DBService.read(page_statement)
        logger.debug("Expenses listed | user_id=%s | count=%s | total=%s", user_id, len(expenses), total)
        return ExpenseListResponse(
            items=[ExpenseResponse.model_validate(expense) for expense in expenses],
            page=filters.page, page_size=filters.page_size, total=total,
            total_pages=(total + filters.page_size - 1) // filters.page_size,
        )

    @staticmethod
    def apply_expense_filters(statement: Select, filters: ExpenseListParams) -> Select:
        """Add the optional filters to an expense query."""
        if filters.category:
            statement = statement.where(Expense.category == filters.category)
        if filters.start_date:
            statement = statement.where(Expense.expense_date >= filters.start_date)
        if filters.end_date:
            statement = statement.where(Expense.expense_date <= filters.end_date)
        if filters.search:
            statement = statement.where(Expense.title.ilike(f"%{filters.search}%"))
        return statement
```

- Query parameters are validated by a schema (`page ≥ 1`, `1 ≤ page_size ≤ 100`, dates parsed, start ≤ end checked); bad values return 400/422 before any query runs.
- The total is counted from the filtered statement, before offset/limit, with `order_by(None)` removed for speed.
- Ordering ends with a unique column so pages are stable.
- Timestamp ranges on datetime columns: `created_at >= start` and `created_at < end_date + 1 day`, in UTC.
- An empty result is 200 with an empty list.

## 3. Search

- PostgreSQL: `column.ilike(f"%{term}%")`. The value is a bound parameter (no SQL injection), but `%` and `_` typed by the user act as wildcards; escape them if exact matching of those characters matters (`ilike(..., escape="\\")`).
- Several fields: `or_(Ticket.title.ilike(pattern), Ticket.description.ilike(pattern))`.
- A leading wildcard can't use a normal B-tree index. That's fine for small tables; for large ones, mention a `pg_trgm` GIN index or full-text search as a later improvement.
- Never fetch rows and filter with Python regex.

## 4. Relationships and N+1

- A response that shows each ticket's comments: `select(Ticket).options(selectinload(Ticket.comments))`, one extra query in total instead of one per ticket.
- A response that shows each comment's author: `joinedload(Comment.author)`.
- Load relationships inside the DBService call: after it returns, the session is closed and lazy loading raises `DetachedInstanceError`.
- Large lists that need only some columns: select those columns (`select(Expense.id, Expense.title)`) and map them to the response schema.

## 5. Aggregates, existence, bulk changes

```python
total_spent = await DBService.read(select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.user_id == user_id), one=True)
email_taken = await DBService.read(select(exists().where(User.email == email)), one=True)
```

Group-by summaries (`select(Expense.category, func.sum(Expense.amount)).group_by(Expense.category)`) return rows, not models; DBService's `read` returns scalars, so add a `read_rows` method to DBService only when the first such query is needed.

Bulk `update()`/`delete()` statements and atomic counters (`stock = stock - 1`) also need a DBService method that executes a write statement and commits; add it when a feature needs it.

## 6. Create and update from schemas

```python
expense = Expense(**payload.model_dump(), user_id=user_id, created_by=user_id, updated_by=user_id)
expense = await DBService.create(expense)

changes = payload.model_dump(exclude_unset=True)
if not changes:
    raise HTTPException(status_code=400, detail="Provide at least one field to update.")
changes["updated_by"] = user_id
expense = await DBService.update(expense, changes)
```

- Load and ownership-check the record first (`select(Expense).where(Expense.id == expense_id, Expense.user_id == user_id)` → 404 if `None`).
- Reject explicit `null` for non-nullable columns before calling update.
- `updated_at` updates itself through `onupdate` on ORM updates.
