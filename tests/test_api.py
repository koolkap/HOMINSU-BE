from io import BytesIO
from json import JSONDecodeError

from app.extensions import db
from app.models import Content, DeviceAction, DeviceSync, MediaAsset, VenueDevice


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
    assert "/api/v1/operator/media" in spec.get_json()["paths"]
    assert "/api/v1/operator/media/{asset_id}" in spec.get_json()["paths"]
    assert "/api/v1/showcase/media" in spec.get_json()["paths"]
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
        self.removals = []

    def upload(self, path, payload, file_options):
        self.uploads.append((path, payload, file_options))

    def get_public_url(self, path):
        return f"https://storage.example/{path}"

    def remove(self, paths):
        self.removals.append(paths)
        return [{"name": path} for path in paths]


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


class FakeS3:
    def __init__(self):
        self.objects = []
        self.deletions = []

    def put_object(self, **kwargs):
        self.objects.append(kwargs)

    def delete_object(self, **kwargs):
        self.deletions.append(kwargs)
        return {"ResponseMetadata": {"HTTPStatusCode": 204}}


class BrokenStorageBucket(FakeStorageBucket):
    def upload(self, path, payload, file_options):
        raise JSONDecodeError("Invalid upstream response", "", 0)


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
    assert data["id"] > 0
    assert data["media_kind"] == "video"
    assert data["is_showcase_ready"] is True
    assert fake.bucket.uploads[0][2]["content-type"] == "video/mp4"
    with app.app_context():
        assert db.session.get(MediaAsset, data["id"]).owner_id == 2
    assert client.delete(f"/api/v1/operator/media/{data['id']}", headers=operator_headers).status_code == 204
    assert fake.bucket.removals == [[data["path"]]]


def test_operator_uploads_media_with_s3_credentials(app, client, operator_headers):
    fake = FakeS3()
    app.config.update({
        "S3_ENDPOINT_URL": "https://project.storage.supabase.co/storage/v1/s3",
        "S3_REGION": "ap-south-1",
        "S3_ACCESS_KEY_ID": "access-key",
        "S3_SECRET_ACCESS_KEY": "secret-key",
        "S3_BUCKET": "hominsu",
        "SUPABASE_URL": "https://project.supabase.co",
    })
    app.extensions["s3"] = fake
    response = client.post(
        "/api/v1/storage/upload",
        data={"file": (BytesIO(b"video"), "tour.mp4", "video/mp4")},
        headers=operator_headers,
    )
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["provider"] == "s3"
    assert data["url"].startswith("https://project.supabase.co/storage/v1/object/public/hominsu/")
    assert fake.objects[0]["Bucket"] == "hominsu"
    assert fake.objects[0]["ContentType"] == "video/mp4"


def test_operator_library_showcase_and_s3_delete(app, client, operator_headers):
    fake = FakeS3()
    app.config.update({
        "STORAGE_PROVIDER": "s3",
        "S3_ENDPOINT_URL": "https://project.storage.supabase.co/storage/v1/s3",
        "S3_REGION": "ap-south-1",
        "S3_ACCESS_KEY_ID": "access-key",
        "S3_SECRET_ACCESS_KEY": "secret-key",
        "S3_BUCKET": "hominsu",
        "SUPABASE_URL": "https://project.supabase.co",
    })
    app.extensions["s3"] = fake
    uploaded = client.post(
        "/api/v1/storage/upload",
        data={"file": (BytesIO(b"video"), "my-vr-tour.mp4", "video/mp4")},
        headers=operator_headers,
    ).get_json()["data"]

    library = client.get("/api/v1/operator/media", headers=operator_headers)
    assert library.status_code == 200
    assert [item["id"] for item in library.get_json()["data"]] == [uploaded["id"]]

    showcase = client.get("/api/v1/showcase/media")
    assert showcase.status_code == 200
    assert showcase.get_json()["data"][0]["title"] == "my vr tour"
    assert "path" not in showcase.get_json()["data"][0]

    deleted = client.delete(f"/api/v1/operator/media/{uploaded['id']}", headers=operator_headers)
    assert deleted.status_code == 204
    assert fake.deletions[0]["Key"] == uploaded["path"]
    assert client.get("/api/v1/showcase/media").get_json()["data"] == []


def test_member_cannot_manage_media(client, member_headers):
    assert client.get("/api/v1/operator/media", headers=member_headers).status_code == 403
    assert client.delete("/api/v1/operator/media/1", headers=member_headers).status_code == 403


def test_explicit_s3_provider_reports_missing_railway_variables(app, client, operator_headers):
    app.config.update({
        "STORAGE_PROVIDER": "s3",
        "S3_ENDPOINT_URL": None,
        "S3_ACCESS_KEY_ID": None,
        "S3_SECRET_ACCESS_KEY": None,
    })
    response = client.post(
        "/api/v1/storage/upload",
        data={"file": (BytesIO(b"video"), "tour.mp4", "video/mp4")},
        headers=operator_headers,
    )
    assert response.status_code == 503
    message = response.get_json()["error"]["message"]
    assert "AWS_ENDPOINT_URL_S3" in message
    assert "AWS_ACCESS_KEY_ID" in message
    assert "AWS_SECRET_ACCESS_KEY" in message


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


def test_malformed_storage_response_returns_bad_gateway(app, client, operator_headers):
    fake = FakeSupabase()
    fake.bucket = BrokenStorageBucket()
    fake.storage = FakeStorage(fake.bucket)
    app.extensions["supabase"] = fake
    response = client.post(
        "/api/v1/storage/upload",
        data={"file": (BytesIO(b"video"), "tour.mp4", "video/mp4")},
        headers=operator_headers,
    )
    assert response.status_code == 502
    assert response.get_json()["error"]["code"] == "storage_error"
