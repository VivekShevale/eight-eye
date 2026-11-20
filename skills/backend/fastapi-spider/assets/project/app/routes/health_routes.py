from fastapi import APIRouter

from app.helpers.health_helper import HealthHelper
from app.schemas.health_schema import HealthResponse

health_router = APIRouter(tags=["Health"])


@health_router.get("/health", response_model=HealthResponse)
async def health_check():
    return await HealthHelper.check_health()
