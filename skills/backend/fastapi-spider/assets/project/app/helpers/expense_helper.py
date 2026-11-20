from fastapi import HTTPException, status
from sqlalchemy import Select, func, select

from app.models.expense import Expense
from app.schemas.expense_schema import ExpenseCreateRequest, ExpenseListParams, ExpenseListResponse, ExpenseResponse, ExpenseUpdateRequest
from app.services.db_service import DBService
from app.utils.log_utils import LogUtils

logger = LogUtils.get_logger(__name__)


class ExpenseHelper:
    """Business logic for expenses (example feature)."""

    @staticmethod
    async def get_owned_expense(expense_id: int, user_id: int) -> Expense:
        """Load an expense owned by the user; another user's expense is reported as missing."""
        expense = await DBService.read(select(Expense).where(Expense.id == expense_id, Expense.user_id == user_id), one=True)
        if expense is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found.")
        return expense

    @staticmethod
    async def create_expense(payload: ExpenseCreateRequest, user_id: int) -> ExpenseResponse:
        """Create an expense; owner and audit fields come from the token, never the body."""
        expense = Expense(**payload.model_dump(), user_id=user_id, created_by=user_id, updated_by=user_id)
        expense = await DBService.create(expense)
        logger.info("Expense created | expense_id=%s | user_id=%s", expense.id, user_id)
        return ExpenseResponse.model_validate(expense)

    @classmethod
    async def list_expenses(cls, user_id: int, params: ExpenseListParams) -> ExpenseListResponse:
        """Return one page of the user's expenses with the requested filters."""
        statement = cls.apply_expense_filters(select(Expense).where(Expense.user_id == user_id), params)
        total = await DBService.read(select(func.count()).select_from(statement.order_by(None).subquery()), one=True)
        page_statement = statement.order_by(Expense.expense_date.desc(), Expense.id.desc()).offset((params.page - 1) * params.page_size).limit(params.page_size)
        expenses = await DBService.read(page_statement)
        logger.debug("Expenses listed | user_id=%s | count=%s | total=%s", user_id, len(expenses), total)
        return ExpenseListResponse(
            items=[ExpenseResponse.model_validate(expense) for expense in expenses],
            page=params.page,
            page_size=params.page_size,
            total=total,
            total_pages=(total + params.page_size - 1) // params.page_size,
        )

    @staticmethod
    def apply_expense_filters(statement: Select, params: ExpenseListParams) -> Select:
        """Add the optional filters to an expense query."""
        if params.category:
            statement = statement.where(Expense.category == params.category)
        if params.start_date:
            statement = statement.where(Expense.expense_date >= params.start_date)
        if params.end_date:
            statement = statement.where(Expense.expense_date <= params.end_date)
        if params.search:
            statement = statement.where(Expense.title.ilike(f"%{params.search}%"))
        return statement

    @classmethod
    async def get_expense(cls, expense_id: int, user_id: int) -> ExpenseResponse:
        """Return one expense owned by the user."""
        expense = await cls.get_owned_expense(expense_id, user_id)
        logger.debug("Expense read | expense_id=%s | user_id=%s", expense_id, user_id)
        return ExpenseResponse.model_validate(expense)

    @classmethod
    async def update_expense(cls, expense_id: int, payload: ExpenseUpdateRequest, user_id: int) -> ExpenseResponse:
        """Apply only the fields the client sent."""
        changes = payload.model_dump(exclude_unset=True)
        if not changes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide at least one field to update.")
        if any(value is None for value in changes.values()):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fields cannot be set to null.")
        expense = await cls.get_owned_expense(expense_id, user_id)
        expense = await DBService.update(expense, {**changes, "updated_by": user_id})
        logger.info("Expense updated | expense_id=%s | user_id=%s | fields=%s", expense_id, user_id, ",".join(changes))
        return ExpenseResponse.model_validate(expense)

    @classmethod
    async def delete_expense(cls, expense_id: int, user_id: int) -> None:
        """Delete an expense owned by the user."""
        expense = await cls.get_owned_expense(expense_id, user_id)
        await DBService.delete(expense)
        logger.info("Expense deleted | expense_id=%s | user_id=%s", expense_id, user_id)
