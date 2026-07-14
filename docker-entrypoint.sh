#!/usr/bin/env bash
# Entrypoint dispatch for the shared SwarmWarm image.
# Usage (via compose `command`): web | worker | beat
set -e

ROLE="${1:-web}"

run_migrations() {
    echo "[entrypoint] Applying database migrations (alembic upgrade head)..."
    alembic upgrade head || echo "[entrypoint] WARNING: alembic upgrade failed (continuing)."
}

case "$ROLE" in
    web)
        run_migrations
        echo "[entrypoint] Starting FastAPI (uvicorn) on :8000"
        exec uvicorn app.main:app --host 0.0.0.0 --port 8000
        ;;
    worker)
        echo "[entrypoint] Starting Celery worker"
        exec celery -A app.core.celery_app worker --loglevel=info
        ;;
    beat)
        echo "[entrypoint] Starting Celery beat scheduler"
        exec celery -A app.core.celery_app beat --loglevel=info
        ;;
    *)
        echo "[entrypoint] Unknown role '$ROLE' (expected web|worker|beat)"
        exit 1
        ;;
esac
