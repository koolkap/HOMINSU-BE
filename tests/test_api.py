from io import BytesIO

from app.extensions import db
from app.models import Content, DeviceAction, DeviceSync, VenueDevice


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"data": {"status": "ok"}}


def test_service_index(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.get_json()["data"]["api_base"] == "/api/v1"
    assert client.get("/api/v1").status_code == 200


def test_openapi_spec_and_swagger_ui(client):
    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    assert spec.get_json()["info"]["title"] == "HOMINSU REST API"
    assert "/api/v1/auth/login" in spec.get_json()["paths"]
    assert "/api/v1/storage/upload" in spec.get_json()["paths"]
    docs = client.get("/docs/")
    assert docs.status_code == 200
    assert b"HOMINSU REST API" in docs.data


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
    created = client.post("/api/v1/operator/devices/actions", json={"device_ids": [device_id], "action": "refresh_catalog", "payload": {"force": True}}, headers=operator_headers)
    assert created.status_code == 201
    with app.app_context():
        action = db.session.get(DeviceAction, created.get_json()["data"]["actions"][0]["id"])
        assert action.status == "pending"
        assert db.session.get(VenueDevice, device_id) is not None


def test_operator_can_sync_fleet(app, client, operator_headers):
    devices = client.get("/api/v1/operator/devices", headers=operator_headers).get_json()["data"]
    device_ids = [device["id"] for device in devices]
    response = client.post("/api/v1/operator/sync", json={"device_ids": device_ids, "payload": {"content_id": 1}}, headers=operator_headers)
    assert response.status_code == 201
    assert response.get_json()["data"]["synced"] == len(device_ids)
    with app.app_context():
        assert len(db.session.scalars(db.select(DeviceSync)).all()) == len(device_ids)


class FakeStorageBucket:
    def __init__(self):
        self.uploads = []

    def upload(self, path, payload, file_options):
        self.uploads.append((path, payload, file_options))

    def get_public_url(self, path):
        return f"https://storage.example/{path}"


class FakeStorage:
    def __init__(self, bucket):
        self.bucket = bucket
        self.requested_bucket = None

    def from_(self, name):
        self.requested_bucket = name
        return self.bucket


class FakeSupabase:
    def __init__(self):
        self.bucket = FakeStorageBucket()
        self.storage = FakeStorage(self.bucket)


def test_upload_requires_operator(client, member_headers):
    file_data = {"file": (BytesIO(b"video"), "tour.mp4", "video/mp4")}
    assert client.post("/api/v1/storage/upload", data=file_data).status_code == 401
    file_data = {"file": (BytesIO(b"video"), "tour.mp4", "video/mp4")}
    assert client.post("/api/v1/storage/upload", data=file_data, headers=member_headers).status_code == 403


def test_operator_uploads_media_to_supabase(app, client, operator_headers):
    fake = FakeSupabase()
    app.extensions["supabase"] = fake
    response = client.post(
        "/api/v1/storage/upload",
        data={"file": (BytesIO(b"video"), "../../tour.mp4", "video/mp4")},
        headers=operator_headers,
    )
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert fake.storage.requested_bucket == "hominsu"
    assert data["path"].startswith("uploads/2/")
    assert data["path"].endswith(".mp4")
    assert "tour" not in data["path"]
    assert data["size"] == 5
    assert fake.bucket.uploads[0][2]["content-type"] == "video/mp4"


def test_upload_validates_type_and_size(app, client, operator_headers):
    app.extensions["supabase"] = FakeSupabase()
    invalid = client.post(
        "/api/v1/storage/upload",
        data={"file": (BytesIO(b"text"), "page.html", "text/html")},
        headers=operator_headers,
    )
    assert invalid.status_code == 400

    app.config["STORAGE_MAX_FILE_SIZE"] = 4
    oversized = client.post(
        "/api/v1/storage/upload",
        data={"file": (BytesIO(b"video"), "tour.mp4", "video/mp4")},
        headers=operator_headers,
    )
    assert oversized.status_code == 413
    assert oversized.get_json()["error"]["code"] == "request_entity_too_large"
