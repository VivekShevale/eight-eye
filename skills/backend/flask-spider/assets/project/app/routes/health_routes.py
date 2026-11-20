from flask import Blueprint

from app.helpers.health_helper import HealthHelper

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health_check():
    return HealthHelper.check_health()
