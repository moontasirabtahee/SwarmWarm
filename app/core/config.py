"""
Backwards-compatible config shim.

All configuration now lives in `app.core.settings`. These module-level names are kept
so existing imports (`from app.core.config import JWT_SECRET_KEY, ...`) keep working.
"""
import logging

from app.core.settings import settings

logger = logging.getLogger("swarmwarm.config")

JWT_SECRET_KEY = settings.SWARMWARM_JWT_SECRET
if not JWT_SECRET_KEY:
    logger.warning(
        "SWARMWARM_JWT_SECRET is not set — using an insecure development fallback. "
        "Set it in your .env before deploying."
    )
    JWT_SECRET_KEY = "dev_insecure_swarmwarm_jwt_secret_do_not_use_in_production"

JWT_ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS
