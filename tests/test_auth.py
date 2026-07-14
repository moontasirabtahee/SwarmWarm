import uuid

from tests.conftest import auth


def _new_email():
    return f"auth_{uuid.uuid4().hex[:8]}@example.com"


def test_signup_login_and_me(client):
    email = _new_email()
    r = client.post("/api/v1/auth/signup", json={"email": email, "password": "password123"})
    assert r.status_code == 201
    assert r.json()["is_verified"] is False

    r = client.post("/api/v1/auth/token", data={"username": email, "password": "password123"})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] and body["refresh_token"]

    r = client.get("/api/v1/auth/me", headers=auth(body["access_token"]))
    assert r.status_code == 200
    assert r.json()["email"] == email


def test_wrong_password_rejected(client):
    email = _new_email()
    client.post("/api/v1/auth/signup", json={"email": email, "password": "password123"})
    r = client.post("/api/v1/auth/token", data={"username": email, "password": "nope"})
    assert r.status_code == 401


def test_duplicate_signup_rejected(client):
    email = _new_email()
    client.post("/api/v1/auth/signup", json={"email": email, "password": "password123"})
    r = client.post("/api/v1/auth/signup", json={"email": email, "password": "password123"})
    assert r.status_code == 400


def test_refresh_rotation(client):
    email = _new_email()
    client.post("/api/v1/auth/signup", json={"email": email, "password": "password123"})
    tok = client.post("/api/v1/auth/token", data={"username": email, "password": "password123"}).json()
    old_refresh = tok["refresh_token"]

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 200
    assert r.json()["refresh_token"] != old_refresh

    # Old refresh token is now revoked.
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 401


def test_protected_requires_token(client):
    assert client.get("/api/v1/mailboxes").status_code == 401
