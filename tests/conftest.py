import pytest

from app import create_app
from app.extensions import db
from app.seed import seed_database


@pytest.fixture()
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite+pysqlite:///:memory:",
        "SQLALCHEMY_ENGINE_OPTIONS": {},
        "JWT_SECRET_KEY": "hominsu-test-secret-key-32-bytes-minimum",
        "CORS_ORIGINS": ["http://localhost"],
    })
    with app.app_context():
        db.create_all()
        seed_database()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, email="member@hominsu.local", password="member1234"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return response.get_json()["data"]["access_token"]


@pytest.fixture()
def member_headers(client):
    return {"Authorization": f"Bearer {login(client)}"}


@pytest.fixture()
def operator_headers(client):
    token = login(client, "operator@hominsu.local", "operator1234")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_headers(client):
    token = login(client, "admin@hominsu.local", "admin1234")
    return {"Authorization": f"Bearer {token}"}
