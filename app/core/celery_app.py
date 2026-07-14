import os
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Read Redis Broker URL from .env, default to localhost
REDIS_BROKER_URL = os.getenv("REDIS_BROKER_URL", "redis://localhost:6379/0")

# Initialize the Celery App instance
app = Celery(
    "swarmwarm",
    broker=REDIS_BROKER_URL,
    backend=REDIS_BROKER_URL,
    include=["app.workers.tasks"]
)

# Enforce explicit enterprise configuration parameters
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task execution timeout limits (e.g. 5 minutes/300 seconds max runtime)
    task_time_limit=300,
    task_soft_time_limit=270,
    
    # Redis visibility timeout (e.g. 1 hour / 3600 seconds)
    # Prevents task duplication if long IMAP search and rescue jobs take time to process
    broker_transport_options={
        "visibility_timeout": 3600
    },
    
    # Concurrency and reliability settings
    task_reject_on_worker_lost=True,
    task_acks_late=True,
)

# Nightly Beat schedule: recompute the P2P allocation graph and dispatch the day's
# warmup tasks at 00:00 UTC (matches the Phase 3 "Beat Clock Strikes 00:00 UTC" spec).
# Referenced by dotted name (no import) so the scheduler stays lazily loaded and
# free of circular-import issues. Run with:  celery -A app.core.celery_app beat
app.conf.beat_schedule = {
    "nightly-swarm-allocation": {
        "task": "app.workers.tasks.run_nightly_swarm_cycle",
        "schedule": crontab(hour=0, minute=0),
    }
}

if __name__ == "__main__":
    app.start()
