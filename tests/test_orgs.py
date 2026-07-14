from app.core import tokens
from app.core.db import create_invitation, get_organization
from tests.conftest import auth


def test_personal_workspace_exists(client, user_token):
    _, token = user_token
    r = client.get("/api/v1/orgs", headers=auth(token))
    assert r.status_code == 200
    assert len(r.json()) >= 1
    assert r.json()[0]["role"] == "owner"


def test_membership_required_for_foreign_org(client, user_token):
    # user A's org
    _, token_a = user_token
    org_id = client.get("/api/v1/orgs", headers=auth(token_a)).json()[0]["id"]

    # a different user B
    import uuid
    email_b = f"orgb_{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/auth/signup", json={"email": email_b, "password": "password123"})
    token_b = client.post("/api/v1/auth/token", data={"username": email_b, "password": "password123"}).json()["access_token"]

    r = client.get(f"/api/v1/orgs/{org_id}/members", headers=auth(token_b))
    assert r.status_code == 403


def test_invitation_accept_flow(client, user_token):
    email_owner, token_owner = user_token
    org_id = client.get("/api/v1/orgs", headers=auth(token_owner)).json()[0]["id"]

    # Invitee signs up
    import uuid
    email_invitee = f"inv_{uuid.uuid4().hex[:8]}@example.com"
    client.post("/api/v1/auth/signup", json={"email": email_invitee, "password": "password123"})
    token_invitee = client.post("/api/v1/auth/token", data={"username": email_invitee, "password": "password123"}).json()["access_token"]

    # Seed an invitation with a known raw token (email delivery is out-of-band).
    owner_id = client.get("/api/v1/auth/me", headers=auth(token_owner)).json()["id"]
    raw = tokens.generate_token()
    create_invitation(org_id=org_id, email=email_invitee, role="member",
                      token_hash=tokens.hash_token(raw), expires_at=tokens.expiry_iso(days=7),
                      invited_by=owner_id)

    # Not a member yet.
    assert client.get(f"/api/v1/orgs/{org_id}/members", headers=auth(token_invitee)).status_code == 403

    # Accept.
    r = client.post("/api/v1/orgs/invitations/accept", json={"token": raw}, headers=auth(token_invitee))
    assert r.status_code == 200

    # Now a member.
    members = client.get(f"/api/v1/orgs/{org_id}/members", headers=auth(token_owner)).json()
    assert email_invitee in [m["email"] for m in members]
