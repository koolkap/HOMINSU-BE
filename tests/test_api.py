from app.extensions import db
from app.models import Content, DeviceAction, VenueDevice


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"data": {"status": "ok"}}


def test_catalog_categories_and_content_filter(client):
    categories = client.get("/api/v1/catalog/categories")
    assert categories.status_code == 200
    assert any(item["slug"] == "culture" for item in categories.get_json()["data"])
    content = client.get("/api/v1/content?category=culture&feed=featured&q=경복궁")
    assert content.status_code == 200
    assert [item["title"] for item in content.get_json()["data"]] == ["경복궁, 시간을 걷다"]


def test_login_and_me(client):
    bad = client.post("/api/v1/auth/login", json={"email": "member@hominsu.local", "password": "wrong"})
    assert bad.status_code == 401
    good = client.post("/api/v1/auth/login", json={"email": "member@hominsu.local", "password": "member1234"})
    assert good.status_code == 200
    token = good.get_json()["data"]["access_token"]
    me = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.get_json()["data"]["role"] == "member"


def test_unlock_with_points_is_idempotent(app, client, member_headers):
    with app.app_context():
        content_id = db.session.scalar(db.select(Content).where(Content.title.like("경복궁%"))).id
    response = client.post(f"/api/v1/content/{content_id}/unlock", json={"method": "points"}, headers=member_headers)
    assert response.status_code == 201
    assert response.get_json()["data"]["wallet"]["points_balance"] == 1200
    repeated = client.post(f"/api/v1/content/{content_id}/unlock", json={"method": "cash"}, headers=member_headers)
    assert repeated.status_code == 200
    assert repeated.get_json()["data"]["already_unlocked"] is True


def test_operator_authorization_and_action(app, client, member_headers, operator_headers):
    denied = client.get("/api/v1/operator/devices", headers=member_headers)
    assert denied.status_code == 403
    devices = client.get("/api/v1/operator/devices", headers=operator_headers)
    assert devices.status_code == 200
    device_id = devices.get_json()["data"][0]["id"]
    created = client.post("/api/v1/operator/devices/actions", json={"device_id": device_id, "action": "refresh_catalog", "payload": {"force": True}}, headers=operator_headers)
    assert created.status_code == 201
    with app.app_context():
        action = db.session.get(DeviceAction, created.get_json()["data"]["id"])
        assert action.status == "pending"
        assert db.session.get(VenueDevice, device_id) is not None
