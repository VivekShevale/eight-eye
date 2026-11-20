from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.helpers.expense_helper import ExpenseHelper
from app.schemas.expense_schema import ExpenseCreateRequest, ExpenseListParams, ExpenseListResponse, ExpenseResponse, ExpenseUpdateRequest
from app.utils.auth_utils import AuthUtils

expense_router = APIRouter(prefix="/api/v1/expenses", tags=["Expenses"])


@expense_router.post("", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(payload: ExpenseCreateRequest, current_user: dict = Depends(AuthUtils.get_current_user)):
    return await ExpenseHelper.create_expense(payload, current_user["user_id"])


@expense_router.get("", response_model=ExpenseListResponse)
async def list_expenses(params: Annotated[ExpenseListParams, Query()], current_user: dict = Depends(AuthUtils.get_current_user)):
    return await ExpenseHelper.list_expenses(current_user["user_id"], params)


@expense_router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(expense_id: int, current_user: dict = Depends(AuthUtils.get_current_user)):
    return await ExpenseHelper.get_expense(expense_id, current_user["user_id"])


@expense_router.patch("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(expense_id: int, payload: ExpenseUpdateRequest, current_user: dict = Depends(AuthUtils.get_current_user)):
    return await ExpenseHelper.update_expense(expense_id, payload, current_user["user_id"])


@expense_router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(expense_id: int, current_user: dict = Depends(AuthUtils.get_current_user)):
    await ExpenseHelper.delete_expense(expense_id, current_user["user_id"])
