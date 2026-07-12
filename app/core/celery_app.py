import os
from celery import Celery
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

if __name__ == "__main__":
    app.start()
