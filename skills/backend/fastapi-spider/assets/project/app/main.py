from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes.auth_routes import auth_router
from app.routes.expense_routes import expense_router
from app.routes.health_routes import health_router
from app.services.db_service import DBService
from app.utils.error_handlers import ErrorHandlers
from app.utils.log_utils import LogUtils

LogUtils.configure_logging()
logger = LogUtils.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create shared clients at startup and close them at shutdown."""
    DBService.connect()
    logger.info("Application started | app=%s", settings.app_name)
    yield
    await DBService.close()
    logger.info("Application stopped")


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
ErrorHandlers.register_handlers(app)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(expense_router)
