from flask import Blueprint
from flask_jwt_extended import jwt_required

from app.helpers.auth_helper import AuthHelper
from app.schemas.auth_schema import LoginRequest, RegisterRequest
from app.utils.request_utils import RequestUtils

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


@auth_bp.post("/register")
def register():
    return AuthHelper.register_user(RequestUtils.parse_body(RegisterRequest))


@auth_bp.post("/login")
def login():
    return AuthHelper.login_user(RequestUtils.parse_body(LoginRequest))


@auth_bp.get("/me")
@jwt_required()
def get_me():
    return AuthHelper.get_current_user()
