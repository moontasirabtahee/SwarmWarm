from app.core.security import encrypt_token, decrypt_token
from app.core.passwords import hash_password, verify_password
from tests.conftest import auth


def test_crypto_roundtrip():
    secret = "smtp_app_password_!@#"
    enc = encrypt_token(secret)
    assert enc != secret
    assert decrypt_token(enc) == secret
    # Tamper detection
    try:
        decrypt_token(enc[:-4] + "AAAA")
        assert False, "tampered ciphertext should not decrypt"
    except ValueError:
        pass


def test_password_hashing():
    h = hash_password("hunter2")
    assert verify_password("hunter2", h)
    assert not verify_password("wrong", h)


def test_account_export(client, user_token):
    _, token = user_token
    r = client.get("/api/v1/account/export", headers=auth(token))
    assert r.status_code == 200
    data = r.json()
    assert "profile" in data and "subscription" in data and "mailboxes" in data


def test_account_delete_requires_password(client):
    import uuid
    email = f"del_{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/auth/signup", json={"email": email, "password": "password123"})
    token = client.post("/api/v1/auth/token", data={"username": email, "password": "password123"}).json()["access_token"]

    # Wrong password -> 403
    assert client.request("DELETE", "/api/v1/account", json={"password": "nope"}, headers=auth(token)).status_code == 403
    # Correct password -> 204
    assert client.request("DELETE", "/api/v1/account", json={"password": "password123"}, headers=auth(token)).status_code == 204
    # Login now fails
    assert client.post("/api/v1/auth/token", data={"username": email, "password": "password123"}).status_code == 401
