def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["database"] == "ok"


def test_root_serves_spa(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "SwarmWarm" in r.text
