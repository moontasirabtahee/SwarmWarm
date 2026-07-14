import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text

from app.core.settings import settings
from app.core.database import engine
from app.api import auth, mailboxes, analytics, stream, admin, billing, orgs, account

# ----- Structured logging -----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("swarmwarm.main")

# ----- Optional Sentry error monitoring -----
if settings.SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=settings.SENTRY_DSN, environment=settings.ENV, traces_sample_rate=0.1)
        logger.info("Sentry monitoring enabled.")
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning("Sentry DSN set but sentry_sdk unavailable: %s", exc)

app = FastAPI(
    title="SwarmWarm REST API Gateway",
    description=(
        "Production-grade control plane API for the SwarmWarm Multi-Tenant P2P Email Warmup Engine. "
        "Handles credential encryption, mailbox fleet CRUD, subscriptions/quotas, teams, and real-time analytics."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — origins come from settings. Bearer-token auth (no cookies), so credentials stay off.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register endpoint routers
app.include_router(auth.router)
app.include_router(mailboxes.router)
app.include_router(analytics.router)
app.include_router(analytics.dashboard_router)
app.include_router(stream.router)
app.include_router(admin.router)
app.include_router(billing.router)
app.include_router(orgs.router)
app.include_router(account.router)

# Mount static folder
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/health", tags=["Ops"])
async def health():
    """Liveness probe — process is up."""
    return {"status": "ok"}


@app.get("/ready", tags=["Ops"])
async def ready():
    """Readiness probe — verifies database connectivity."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception as exc:
        logger.error("Readiness check failed: %s", exc)
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "error"})


@app.get("/", tags=["Gateway Status"])
async def root():
    """Serves the SwarmWarm frontend UI dashboard SPA."""
    return FileResponse("app/static/index.html")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
