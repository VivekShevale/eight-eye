from datetime import timedelta

from flask import Flask
from flask_cors import CORS

from app.config import settings
from app.extensions import db, jwt, migrate
from app.models import expense, user  # noqa: F401  (registers every model for Flask-Migrate)
from app.routes.auth_routes import auth_bp
from app.routes.expense_routes import expense_bp
from app.routes.health_routes import health_bp
from app.services.db_service import DBService
from app.utils.auth_utils import AuthUtils
from app.utils.error_handlers import ErrorHandlers
from app.utils.log_utils import LogUtils

logger = LogUtils.get_logger(__name__)


def create_app() -> Flask:
    """Build the Flask application: config, logging, extensions, handlers, blueprints."""
    LogUtils.configure_logging()
    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI=settings.database_url,
        SQLALCHEMY_ENGINE_OPTIONS=DBService.get_pool_options(),
        JWT_SECRET_KEY=settings.jwt_secret_key,
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(minutes=settings.access_token_expire_minutes),
    )

    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=settings.database_url.startswith("sqlite"))
    jwt.init_app(app)
    jwt.user_lookup_loader(AuthUtils.load_user)
    CORS(app, origins=settings.cors_origins, supports_credentials=True)
    ErrorHandlers.register_handlers(app, jwt)

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(expense_bp)

    logger.info("Application created | app=%s", settings.app_name)
    return app
