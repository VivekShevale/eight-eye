from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from app.models.base import Base

# Created here without an app and bound in create_app(), so any module can import them without circular imports.
db = SQLAlchemy(model_class=Base)
migrate = Migrate()
jwt = JWTManager()
