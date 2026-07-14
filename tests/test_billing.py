from tests.conftest import auth

_MAILBOX = {
    "smtp_host": "smtp.x.io", "smtp_port": 587,
    "imap_host": "imap.x.io", "imap_port": 993,
    "app_password": "pw12345", "provider": "custom",
    "use_ssl": False, "daily_send_limit": 500,
}


def _onboard(client, token, email):
    payload = dict(_MAILBOX, email=email)
    return client.post("/api/v1/mailboxes/onboard", json=payload, headers=auth(token))


def test_plans_listed(client):
    r = client.get("/api/v1/billing/plans")
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()}
    assert {"free", "pro", "scale"} <= ids


def test_default_subscription_is_free(client, user_token):
    _, token = user_token
    r = client.get("/api/v1/billing/subscription", headers=auth(token))
    assert r.status_code == 200
    assert r.json()["plan_id"] == "free"


def test_quota_enforced_and_daily_limit_clamped(client, user_token):
    email, token = user_token
    # Free plan allows 2 mailboxes; daily limit clamped to plan cap (40).
    r1 = _onboard(client, token, f"a_{email}")
    assert r1.status_code == 201
    assert r1.json()["daily_send_limit"] == 40  # clamped from 500

    r2 = _onboard(client, token, f"b_{email}")
    assert r2.status_code == 201

    r3 = _onboard(client, token, f"c_{email}")
    assert r3.status_code == 402  # over free-plan mailbox ceiling


def test_dev_checkout_upgrades_plan(client, user_token):
    email, token = user_token
    client.post("/api/v1/billing/checkout", json={"plan_id": "pro"}, headers=auth(token))
    r = client.get("/api/v1/billing/subscription", headers=auth(token))
    assert r.json()["plan_id"] == "pro"
    assert r.json()["max_mailboxes"] == 10
