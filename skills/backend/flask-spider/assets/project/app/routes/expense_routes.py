from flask import Blueprint
from flask_jwt_extended import jwt_required

from app.helpers.expense_helper import ExpenseHelper
from app.schemas.expense_schema import ExpenseCreateRequest, ExpenseListParams, ExpenseUpdateRequest
from app.utils.auth_utils import AuthUtils
from app.utils.request_utils import RequestUtils

expense_bp = Blueprint("expenses", __name__, url_prefix="/api/v1/expenses")


@expense_bp.post("")
@jwt_required()
def create_expense():
    return ExpenseHelper.create_expense(RequestUtils.parse_body(ExpenseCreateRequest), AuthUtils.get_current_user_id())


@expense_bp.get("")
@jwt_required()
def list_expenses():
    return ExpenseHelper.list_expenses(AuthUtils.get_current_user_id(), RequestUtils.parse_query(ExpenseListParams))


@expense_bp.get("/<int:expense_id>")
@jwt_required()
def get_expense(expense_id: int):
    return ExpenseHelper.get_expense(expense_id, AuthUtils.get_current_user_id())


@expense_bp.patch("/<int:expense_id>")
@jwt_required()
def update_expense(expense_id: int):
    return ExpenseHelper.update_expense(expense_id, RequestUtils.parse_body(ExpenseUpdateRequest), AuthUtils.get_current_user_id())


@expense_bp.delete("/<int:expense_id>")
@jwt_required()
def delete_expense(expense_id: int):
    return ExpenseHelper.delete_expense(expense_id, AuthUtils.get_current_user_id())
