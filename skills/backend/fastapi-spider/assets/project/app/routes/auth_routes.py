from fastapi import APIRouter, Depends, status

from app.helpers.auth_helper import AuthHelper
from app.schemas.auth_schema import CurrentUserResponse, LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.utils.auth_utils import AuthUtils

auth_router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


@auth_router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest):
    return await AuthHelper.register_user(payload)


@auth_router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    return await AuthHelper.login_user(payload)


@auth_router.get("/me", response_model=CurrentUserResponse)
async def get_me(current_user: dict = Depends(AuthUtils.get_current_user)):
    return current_user
