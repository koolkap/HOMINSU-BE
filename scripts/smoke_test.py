"""End-to-end smoke test against SQLite (no Docker/Postgres needed).

Run: python scripts/smoke_test.py
Covers: social login, /me, recharge, deduct, insufficient balance,
content create, purchase, SRS on_publish/on_unpublish webhooks.
"""

import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./smoke_test.db"
os.environ["CORS_ORIGINS"] = '["*"]'

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def receive_until(ws, event: str, limit: int = 10) -> dict:
    """Skip broadcasts (device_connected, etc.) until the wanted event arrives."""
    for _ in range(limit):
        message = ws.receive_json()
        if message.get("event") == event:
            return message
    raise AssertionError(f"event {event!r} not received within {limit} messages")


def main() -> None:
    # Enter the client as a context manager so the app lifespan (init_db) runs.
    with TestClient(app) as client:
        run_checks(client)


def run_checks(client: TestClient) -> None:
    # 1. health
    assert client.get("/health").json()["status"] == "ok"

    # 2. social login (signup)
    r = client.post(
        "/api/v1/auth/social-login",
        json={"email": "ajit@hominsh.com", "name": "Ajit", "provider": "kakao"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    # 3. /me
    me = client.get("/api/v1/auth/me", headers=auth).json()
    assert me["email"] == "ajit@hominsh.com" and me["points_balance"] == 0

    # 4. recharge 10,000 KRW -> 11,000P
    r = client.post("/api/v1/points/recharge", json={"amount_krw": 10000}, headers=auth)
    assert r.status_code == 200 and r.json()["points_balance"] == 11000, r.text

    # 5. deduct 1,000P
    r = client.post(
        "/api/v1/points/deduct", json={"amount": 1000, "description": "tip"}, headers=auth
    )
    assert r.json()["points_balance"] == 10000, r.text

    # 6. insufficient balance rejected
    r = client.post("/api/v1/points/deduct", json={"amount": 999999}, headers=auth)
    assert r.status_code == 400, r.text

    # 7. create live content with a stream key
    r = client.post(
        "/api/v1/contents",
        json={"title": "Concert 360", "type": "LIVE_360", "stream_key": "insta-001", "price_points": 500},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    content_id = r.json()["id"]

    # 8. purchase content -> balance 9500
    r = client.post(f"/api/v1/contents/{content_id}/purchase", headers=auth)
    assert r.json()["remaining_balance"] == 9500, r.text

    # 9. SRS on_publish / on_unpublish
    r = client.post("/api/v1/srs/on_publish", json={"action": "on_publish", "stream": "insta-001"})
    assert r.status_code == 200 and r.json() == {"code": 0}, r.text
    live = client.get("/api/v1/contents", params={"live_only": True}).json()
    assert len(live) == 1 and live[0]["is_live"] and live[0]["media_url"].endswith("insta-001.m3u8")
    r = client.post("/api/v1/srs/on_unpublish", json={"action": "on_unpublish", "stream": "insta-001"})
    assert r.json() == {"code": 0}
    assert client.get(f"/api/v1/contents/{content_id}").json()["is_live"] is False

    # 10. device registry
    r = client.post("/api/v1/fleet/devices", json={"id": "HS-01", "model": "Meta Quest 3"})
    assert r.status_code == 201, r.text
    assert client.get("/api/v1/fleet/devices").json()[0]["id"] == "HS-01"

    # 11. WebSocket fleet flow: heartbeat telemetry + SYNC_PLAY dispatch
    with client.websocket_connect("/ws/operator") as operator:
        with client.websocket_connect("/ws/device/HS-01") as device:
            # device heartbeat -> operator receives telemetry
            device.send_json(
                {
                    "event": "heartbeat",
                    "battery_level": 87.5,
                    "ip_address": "192.168.0.42",
                    "status": "ONLINE",
                }
            )
            telemetry = receive_until(operator, "telemetry")
            assert telemetry["event"] == "telemetry" and telemetry["device_id"] == "HS-01", telemetry
            assert telemetry["battery_level"] == 87.5

            # operator command -> device receives SYNC_PLAY
            operator.send_json(
                {
                    "event": "trigger_sync_play",
                    "device_ids": ["HS-01"],
                    "video_url": "http://localhost:8080/live/insta-001.m3u8",
                }
            )
            ack = receive_until(operator, "sync_play_dispatched")
            assert ack["delivery"] == {"HS-01": True}, ack
            command = device.receive_json()
            assert command["command"] == "SYNC_PLAY" and command["video_url"].endswith("insta-001.m3u8"), command
            assert isinstance(command["timestamp"], float)

    # heartbeat persisted to the devices table
    assert client.get("/api/v1/fleet/devices/HS-01").json()["battery_level"] == 87.5

    print("SMOKE_TEST_OK - all 11 checks passed")


if __name__ == "__main__":
    main()
