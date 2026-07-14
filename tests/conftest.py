"""
Pytest fixtures.

Points the app at an isolated temporary SQLite database and sets hermetic secrets
BEFORE any app module is imported, so tests never touch the dev database or require a
populated .env.
"""
import os
import tempfile

# Must run before `app.*` is imported anywhere.
_TMP_DB = os.path.join(tempfile.gettempdir(), "swarmwarm_pytest.db")
if os.path.exists(_TMP_DB):
    os.remove(_TMP_DB)

os.environ["DATABASE_URL"] = "sqlite:///" + _TMP_DB.replace("\\", "/")
os.environ["SWARMWARM_SECRET_KEY"] = "A" * 43 + "="        # 32 zero-bytes, valid base64
os.environ["SWARMWARM_JWT_SECRET"] = "pytest-jwt-secret"
os.environ["EMAIL_BACKEND"] = "console"
os.environ["STRIPE_SECRET_KEY"] = ""                       # dev-mode billing
os.environ.pop("VALIDATE_MAILBOX_CONNECTIONS", None)       # keep onboarding lightweight

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def user_token(client):
    """A freshly registered, logged-in non-admin user; returns (email, access_token)."""
    import uuid
    email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/auth/signup", json={"email": email, "password": "password123"})
    resp = client.post("/api/v1/auth/token", data={"username": email, "password": "password123"})
    return email, resp.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
