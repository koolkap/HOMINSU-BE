# Hominsu VR Studio — Backend

Asynchronous Python backend for **Hominsu VR Studio**: a live 360° VR streaming engine and
enterprise VR headset fleet-management platform.

## Stack

| Layer | Technology |
|---|---|
| Language / Framework | Python 3.11+, FastAPI (async) |
| ASGI Server | Uvicorn |
| Database | PostgreSQL 17 (local install; Docker compose file also provided) |
| ORM | SQLAlchemy 2 (async); Alembic migrations for PostgreSQL |
| Real-time | Native WebSockets (`python-socketio` available as an alternative) |
| Media Server | Simple Realtime Server (SRS v5, Docker) — RTMP ingest → HLS |
| Auth | JWT (python-jose) + Passlib/bcrypt |

## Project Structure

```
app/
├── api/
│   ├── deps.py                    # get_current_user JWT dependency
│   └── v1/
│       ├── endpoints/
│       │   ├── auth.py            # POST /auth/social-login, GET /auth/me
│       │   ├── points.py          # POST /points/recharge, /points/deduct
│       │   ├── content.py         # CRUD + purchase + viewer counter
│       │   ├── fleet.py           # device registry + /ws/device, /ws/operator
│       │   └── srs_webhooks.py    # SRS on_publish / on_unpublish callbacks
│       └── router.py
├── core/                          # config, async engine/session, JWT security
├── models/                        # users, point_transactions, contents, devices
├── schemas/                       # Pydantic request/response models
├── websockets/connection_manager.py
└── main.py
docker-compose.local.yml           # PostgreSQL + SRS
srs.conf                           # SRS v5 config (HLS + http_hooks → FastAPI)
scripts/smoke_test.py              # end-to-end test (SQLite, no Docker needed)
```

## Local Ports

| Service | Port |
|---|---|
| FastAPI | 8000 |
| PostgreSQL | 5432 |
| SRS RTMP ingest | 1935 |
| SRS HTTP / HLS playback | 8080 |
| SRS HTTP API / WebRTC | 1985 |

## Quickstart

The app is configured for the local `hominsu` PostgreSQL database
(`postgresql+asyncpg://hominsu:hominsu_dev_password@localhost:5432/hominsu`). Tables are
auto-created on startup, and a demo user (`dev@hominsh.com`, 50,000P), demo content and a demo
device (`HS-01`) are seeded for easy Swagger testing.

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Swagger UI: **http://localhost:8000/docs**

The database and role are created once with:

```sql
CREATE USER hominsu WITH PASSWORD 'hominsu_dev_password';
CREATE DATABASE hominsu OWNER hominsu;
GRANT ALL PRIVILEGES ON DATABASE hominsu TO hominsu;
```

### Optional: SRS media server via Docker (for RTMP ingest / HLS)

Interactive docs: http://localhost:8000/docs

## Verification

```bash
# Full end-to-end test on SQLite (no Docker required):
pip install aiosqlite
PYTHONPATH=. python scripts/smoke_test.py
```

## API Reference

### Auth (`/api/v1/auth`)
- `POST /social-login` — `{email, name, provider}` → upserts the user, returns `{access_token, user}`.
- `GET /me` — bearer token → profile incl. `points_balance` and `subscription_tier`.

### Point Economy (`/api/v1/points`)
- `POST /recharge` — `{amount_krw}` → points at 1.1× (10,000 KRW → 11,000 P); writes a `RECHARGE` transaction.
- `POST /deduct` — `{amount, description}` → validates balance, writes a negative `SPEND` transaction.
- `GET /transactions` — last 100 transactions of the current user.

### Contents (`/api/v1/contents`)
- `POST /` — create VOD / LIVE_360 / SHORT_FORM content (assign a `stream_key` for live).
- `GET /` — list (`?type=LIVE_360&live_only=true`), `GET /{id}`, `PATCH /{id}`.
- `POST /{id}/purchase` — spends `price_points`, returns the playable `media_url`.
- `POST /{id}/view` — bumps `viewer_count`.

### Fleet (`/api/v1/fleet`)
- `GET /devices`, `POST /devices`, `GET /devices/{id}` — headset registry (`HS-01` style IDs).

### SRS Webhooks (`/api/v1/srs`)
- `POST /on_publish` — extracts the stream key, sets `contents.is_live = true`, sets the HLS
  `media_url`, broadcasts `live_started` to operators. Returns `{"code": 0}`.
- `POST /on_unpublish` — sets `is_live = false`, broadcasts `live_stopped`.

## WebSocket Protocol

### VR Headset — `/ws/device/{device_id}`
```jsonc
// headset → server
{"event": "heartbeat", "battery_level": 87.5, "ip_address": "192.168.0.42", "status": "ONLINE"}
// server → headset
{"command": "SYNC_PLAY", "video_url": "http://localhost:8080/live/key.m3u8", "timestamp": 1724150000.123}
```
Heartbeats update the `devices` row (`battery_level`, `ip_address`, `status`, `last_heartbeat`)
and are relayed to every operator console as `telemetry` events. Disconnect marks the device `OFFLINE`.

### Operator Console — `/ws/operator`
```jsonc
// dashboard → server
{"event": "trigger_sync_play", "device_ids": ["HS-01", "HS-02"], "video_url": "http://…m3u8"}
// server → dashboard
{"event": "sync_play_dispatched", "video_url": "http://…m3u8", "delivery": {"HS-01": true, "HS-02": false}}
```
Operators also receive `device_connected` / `device_disconnected` / `telemetry` / `live_started` / `live_stopped`.

## Streaming a Live 360 Event

1. Create live content: `POST /api/v1/contents` with `type: "LIVE_360"`, `stream_key: "insta-001"`.
2. Push video from OBS or an Insta360 camera to `rtmp://localhost:1935/live/insta-001`.
3. SRS calls `/api/v1/srs/on_publish` → content goes live, operators get `live_started`.
4. Play the generated HLS: `http://localhost:8080/live/insta-001.m3u8`.
5. Stop publishing → `on_unpublish` → content marked offline.

## Notes

- Tables are created via `Base.metadata.create_all()` for local development;
  Alembic migrations are available under `alembic/versions/` when explicit
  schema versioning is needed for the local PostgreSQL database.
- SRS reaches the API at `host.docker.internal:8000` (works with Docker Desktop; the compose file
  also adds the `host-gateway` mapping for Linux hosts).
- Change `SECRET_KEY` (and DB credentials) via `.env` before any real deployment.
