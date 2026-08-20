# Hominsu VR Studio: Execution, Verification, and Architecture Audit

This guide matches the current repository. It covers the local PostgreSQL + SRS stack, the
FastAPI service, the RTMP-to-HLS verification path, and a real WebSocket fleet test.

## Current implementation audit

### What is implemented

The checked-in service currently provides:

- Async FastAPI routes under `/api/v1`.
- Async SQLAlchemy models for users, point transactions, content, and VR devices.
- JWT bearer authentication for the REST user, point, and content-purchase flows.
- Point recharge, deduction, transaction history, content purchase, and viewer-count routes.
- SRS `on_publish` and `on_unpublish` callbacks that update live state and notify connected operator sockets.
- Native WebSockets at `/ws/device/{device_id}` and `/ws/operator`.
- Device heartbeat persistence and `SYNC_PLAY` dispatch.
- Docker Compose configuration for PostgreSQL 15 and SRS v5.

### Findings and production actions

| Priority | Finding in the current code | Risk | Required action before production |
|---|---|---|---|
| **P0** | Point deduction checks `user.points_balance` in Python and then writes a new balance. | Two concurrent deductions can both pass the balance check and lose an update, or spend more points than the account owns. | Use a single transaction with `SELECT ... FOR UPDATE`, or an atomic `UPDATE users SET points_balance = points_balance - :amount WHERE id = :id AND points_balance >= :amount`, then insert the ledger row only when the update succeeds. |
| **P0** | Social login trusts the client-provided `email`, `name`, and `provider`. | A caller can submit another person’s email and receive a JWT for that account. | Verify Kakao/Google access or ID tokens server-side; derive the provider subject and verified email from the provider response. Add issuer, audience, and subject checks. |
| **P0** | REST fleet registration/control and both WebSocket endpoints have no authentication or authorization. | Any network caller can register devices, read fleet telemetry, and issue `SYNC_PLAY` commands. | Authenticate WebSockets during the handshake, authenticate fleet REST routes, and enforce operator/device roles and device ownership. |
| **P0** | WebSocket connections are held in an in-process dictionary/set. | Multiple Uvicorn workers or multiple API replicas cannot see each other’s devices or operators. | Use one connection-owning gateway with sticky routing, or add Redis Pub/Sub (or another broker) for cross-process events. Keep device identity and command state in PostgreSQL/Redis. |
| **P1** | SRS hooks accept requests without a signature/shared secret and do not validate the SRS action, vhost, app, or stream fields. | A forged request can mark content live/offline; malformed input can produce a `None` stream URL. | Add an internal network policy plus HMAC/shared-secret validation, strict payload validation, safe URL parsing, and an explicit response policy for unknown stream keys. |
| **P1** | A camera/network failure may not generate `on_unpublish`; live state depends on the callback. | Content can remain live after an unexpected SRS or camera failure. | Store `last_media_event_at`, run a reconciliation worker against SRS HTTP API, and expire live state after a bounded TTL. Alert on stale publishers. |
| **P1** | Reconnect cleanup removes a device by `device_id` only. | If an old socket closes after a new socket has reconnected, the old handler can remove the new socket and mark the device offline. | Disconnect by `(device_id, websocket_instance_id)` and only update offline state if the closing connection is still the active connection. |
| **P1** | There is no application-level heartbeat timeout, command acknowledgement, or reconnect backoff protocol. | Half-open sockets and undelivered commands can look healthy; synchronized playback cannot be confirmed. | Add server/device ping-pong and a heartbeat deadline, exponential reconnect backoff, command IDs, device ACKs, expiry timestamps, and retry/dead-letter handling. |
| **P1** | A purchase can be repeated and the point deduction has no idempotency key or entitlement table. | Retries or repeated unlock requests can charge a user more than once for the same content. | Add `idempotency_key`, a unique purchase/entitlement record per user/content, and an atomic “already unlocked” check. |
| **P1** | The requested 15-second preview lock and ad-reward flow are not represented in the current models or routes; `/me` also returns the schema default for `subscription_tier` rather than a persisted tier. | The paywall can be bypassed or cannot reliably grant an ad reward/subscription benefit. | Add preview-session state, verified ad-reward callbacks, entitlements/subscription fields, and enforce playback authorization at the media-token or playback API boundary. |
| **P1** | The database needs a versioned schema workflow. | Untracked schema changes can make environments diverge. | Use the checked-in Alembic migration under `alembic/versions/` and run `alembic upgrade head` against the target PostgreSQL database. |
| **P2** | Operator broadcasts are sent sequentially, and there is no bounded queue or timeout. | One slow socket can delay telemetry to every other operator. | Send concurrently with per-socket timeouts, remove failed sockets, and use bounded queues for high-rate telemetry. |
| **P2** | `/health` does not check database or SRS readiness. | A process can report healthy while dependencies are unavailable. | Split liveness and readiness checks and include database connectivity and SRS API reachability in readiness. |
| **P2** | The local default enables `DEBUG` and contains a fallback secret. | Debug seeding and a known JWT secret are unsafe if deployed accidentally. | Require an explicit environment, fail startup when the default secret is used outside local development, and disable demo seeding in staging/production. |

The architecture is suitable for a local single-process demonstration and for validating the media
pipeline. The P0/P1 items above are release gates for a multi-tenant or revenue-bearing deployment.

### Reference transaction pattern for the P0 point race

The deduction path should perform the balance check and decrement in one database transaction. A
minimal SQLAlchemy 2.x pattern is:

```python
from fastapi import HTTPException, status
from sqlalchemy import update

async with db.begin():
    result = await db.execute(
        update(User)
        .where(User.id == user_id, User.points_balance >= amount)
        .values(points_balance=User.points_balance - amount)
    )
    if result.rowcount != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient balance",
        )

    db.add(PointTransaction(
        user_id=user_id,
        amount=-amount,
        type=TransactionType.SPEND,
        description=description,
    ))
```

For PostgreSQL, `SELECT ... FOR UPDATE` around the user row is also valid. The ledger insert and
the balance update must commit or roll back together; never commit the balance change separately.

## Prerequisites

Install the following on the development machine:

1. Docker Desktop (or Docker Engine) with Docker Compose v2.
2. Python 3.11 or newer. Python 3.12 is supported by the current dependencies.
3. Git.
4. FFmpeg for command-line media testing, or OBS Studio for camera/scene testing.
5. `curl` (on Windows use `curl.exe` so PowerShell does not resolve the alias).
6. A terminal capable of opening multiple sessions.

Confirm the tools before starting:

```bash
docker --version
docker compose version
python --version
ffmpeg -version
curl --version
```

On Windows PowerShell, `py -3.11 --version` is also acceptable when creating the virtual
environment.

## Local service map

| Service | Address |
|---|---|
| FastAPI | `http://localhost:8000` |
| Swagger UI | `http://localhost:8000/docs` |
| PostgreSQL | `localhost:5432` |
| SRS RTMP ingest | `rtmp://localhost:1935` |
| SRS HLS server | `http://localhost:8080` |
| SRS HTTP API/WebRTC | `http://localhost:1985` |
| Device WebSocket | `ws://localhost:8000/ws/device/{device_id}` |
| Operator WebSocket | `ws://localhost:8000/ws/operator` |

## Step 1: Start PostgreSQL and SRS

Run this from the repository root. The Compose file mounts the checked-in `srs.conf` into the
SRS container at `/usr/local/srs/conf/srs.conf` and maps `host.docker.internal` back to the host
so SRS can call FastAPI webhooks.

```bash
docker compose -f docker-compose.local.yml up -d postgres srs
docker compose -f docker-compose.local.yml ps
docker compose -f docker-compose.local.yml logs --tail=100 postgres srs
```

Wait until PostgreSQL reports healthy before initializing the application database:

```bash
docker compose -f docker-compose.local.yml exec postgres pg_isready -U hominsu -d hominsu
```

The Compose file is the recommended path because it mounts the custom SRS configuration. If
Compose is not being used, the equivalent Docker commands are below; use these instead of the
Compose command, not in addition to it:

```bash
docker network create hominsu-local 2>/dev/null || true

docker run -d --name hominsu-postgres --network hominsu-local \
  -e POSTGRES_USER=hominsu \
  -e POSTGRES_PASSWORD=hominsu_dev_password \
  -e POSTGRES_DB=hominsu \
  -p 5432:5432 \
  postgres:15-alpine

docker run -d --name hominsu-srs --network hominsu-local \
  --add-host=host.docker.internal:host-gateway \
  -p 1935:1935 -p 1985:1985 -p 8080:8080 \
  -v "$(pwd)/srs.conf:/usr/local/srs/conf/srs.conf:ro" \
  ossrs/srs:5
```

On PowerShell, use this volume form for the standalone SRS command:

```powershell
-v "${PWD}\srs.conf:/usr/local/srs/conf/srs.conf:ro"
```

If a previous local stack owns a port, inspect it before changing the Compose file:

```bash
docker ps --format "table {{.Names}}\t{{.Ports}}"
```

## Step 2: Create the Python environment and initialize the database

### macOS/Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install websocket-client
cp .env.example .env
```

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install websocket-client
Copy-Item .env.example .env
```

Edit `.env` and set a local configuration equivalent to the following. Keep `DEBUG=true` only
for local development; use a generated secret and exact frontend origins outside localhost.

```dotenv
DATABASE_URL=postgresql+asyncpg://hominsu:hominsu_dev_password@localhost:5432/hominsu
DEBUG=true
SECRET_KEY=replace-this-with-a-long-random-value
ACCESS_TOKEN_EXPIRE_MINUTES=1440
SRS_HLS_BASE_URL=http://localhost:8080
KRW_TO_POINTS_RATE=1.1
CORS_ORIGINS=["http://localhost:3000"]
```

Generate a suitable local secret with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Current schema initialization

The current application calls `Base.metadata.create_all()` during FastAPI startup. The same
operation can be run explicitly after PostgreSQL is ready:

```bash
python -c "import asyncio; from app.core.database import init_db; asyncio.run(init_db())"
```

The repository also contains a checked-in SQL migration for the former hosted
database setup, but it is not needed for this local-only configuration. Use
the local Alembic migration against Docker PostgreSQL:

```bash
alembic upgrade head
```

For a clean local database, `DEBUG=true` also creates the tables and seeds demo
records during FastAPI startup. Use either automatic startup initialization or
`alembic upgrade head`; do not run both when you need a strict migration-only
workflow.

## Step 3: Start FastAPI

Start the API from the repository root in a terminal where the virtual environment is active:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The startup lifecycle creates local tables and, when `DEBUG=true`, seeds a demo user, a demo
content item, and `HS-01`. Verify the process from a second terminal:

```bash
curl --fail --show-error http://localhost:8000/health
```

Expected response shape:

```json
{"status":"ok","app":"Hominsu VR Studio API","version":"0.1.0"}
```

Open the API contract at <http://localhost:8000/docs>.

## Step 4: Verify the RTMP-to-HLS media pipeline

### 4.1 Create a matching live content record

SRS can generate HLS without a content row, but the `on_publish` webhook only marks a content
record live when its `stream_key` matches. Create the row before pushing the stream.

PowerShell:

```powershell
$login = Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/v1/auth/social-login `
  -ContentType 'application/json' `
  -Body '{"email":"dev-local@example.com","name":"Local Operator","provider":"local"}'

$headers = @{ Authorization = "Bearer $($login.access_token)" }
$content = Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/v1/contents `
  -Headers $headers `
  -ContentType 'application/json' `
  -Body '{"title":"Local 360 Test","type":"LIVE_360","stream_key":"insta-001","price_points":0}'

$content | ConvertTo-Json
```

The same flow with `curl` on macOS/Linux:

```bash
TOKEN=$(curl -fsS -X POST http://localhost:8000/api/v1/auth/social-login \
  -H 'content-type: application/json' \
  -d '{"email":"dev-local@example.com","name":"Local Operator","provider":"local"}' \
  | python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

curl -fsS -X POST http://localhost:8000/api/v1/contents \
  -H "authorization: Bearer ${TOKEN}" \
  -H 'content-type: application/json' \
  -d '{"title":"Local 360 Test","type":"LIVE_360","stream_key":"insta-001","price_points":0}'
```

### 4.2 Push a test stream

Use an equirectangular 360 video when available. For a pipeline-only test, any valid MP4 is
sufficient. The following FFmpeg command produces a synthetic video and audio source, so it does
not require a media file:

```bash
ffmpeg -re \
  -f lavfi -i "testsrc2=size=1920x1080:rate=30" \
  -f lavfi -i "sine=frequency=1000:sample_rate=48000" \
  -c:v libx264 -preset veryfast -tune zerolatency -pix_fmt yuv420p \
  -c:a aac -ar 48000 -f flv \
  rtmp://localhost:1935/live/insta-001
```

To use a local video instead:

```bash
ffmpeg -re -stream_loop -1 -i ./sample-360.mp4 \
  -c:v libx264 -preset veryfast -tune zerolatency \
  -c:a aac -f flv rtmp://localhost:1935/live/insta-001
```

In OBS, set **Settings → Stream → Service** to **Custom**, set the server to
`rtmp://localhost:1935/live`, and set the stream key to `insta-001`.

### 4.3 Check HLS output

Wait at least one HLS fragment interval (normally 5–10 seconds), then run:

```bash
curl --fail --show-error --location http://localhost:8080/live/insta-001.m3u8
```

The response must be an HLS playlist containing `#EXTM3U` and one or more media segment
references. A 404 during the first few seconds is expected while SRS creates the playlist.

Verify that the backend processed the SRS publish hook:

```bash
curl --fail --show-error 'http://localhost:8000/api/v1/contents?live_only=true'
```

The `insta-001` record should have `is_live: true` and a media URL ending in
`/live/insta-001.m3u8`. Watch both logs if it does not:

```bash
docker compose -f docker-compose.local.yml logs -f srs
```

Stop FFmpeg with `Ctrl+C`. SRS should call `on_unpublish`; verify that the content becomes
offline:

```bash
curl --fail --show-error 'http://localhost:8000/api/v1/contents?live_only=true'
```

For isolated webhook testing, the current endpoint returns SRS’s required acceptance response:

```bash
curl --fail --show-error -X POST http://localhost:8000/api/v1/srs/on_publish \
  -H 'content-type: application/json' \
  -d '{"action":"on_publish","stream":"insta-001"}'
```

Expected response:

```json
{"code":0}
```

## Step 5: Test the headset/operator WebSocket flow

Install the local test client if it was not installed above:

```bash
python -m pip install websocket-client
```

The following is a standalone client test for the current protocol. Save it as
`scripts/fleet_ws_test.py` or paste it into a temporary file:

```python
"""Exercise one headset heartbeat and one operator SYNC_PLAY command."""

from __future__ import annotations

import argparse
import json
import time
from typing import Any

from websocket import WebSocket, create_connection


def receive_event(socket: WebSocket, event_name: str, timeout: float = 10.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = max(0.1, deadline - time.monotonic())
        socket.settimeout(remaining)
        message = json.loads(socket.recv())
        if message.get("event") == event_name:
            return message
    raise TimeoutError(f"Timed out waiting for {event_name!r}")


def ws_base(http_base: str) -> str:
    return http_base.replace("https://", "wss://").replace("http://", "ws://").rstrip("/")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--device-id", default="HS-01")
    parser.add_argument("--video-url", default="http://localhost:8080/live/insta-001.m3u8")
    args = parser.parse_args()

    base = ws_base(args.base_url)
    operator = create_connection(f"{base}/ws/operator", timeout=10)
    device = create_connection(f"{base}/ws/device/{args.device_id}", timeout=10)

    try:
        device.send(json.dumps({
            "event": "heartbeat",
            "battery_level": 87.5,
            "ip_address": "127.0.0.1",
            "status": "ONLINE",
        }))
        telemetry = receive_event(operator, "telemetry")
        assert telemetry["device_id"] == args.device_id
        print("telemetry:", json.dumps(telemetry))

        operator.send(json.dumps({
            "event": "trigger_sync_play",
            "device_ids": [args.device_id],
            "video_url": args.video_url,
        }))
        dispatch = receive_event(operator, "sync_play_dispatched")
        command = json.loads(device.recv())
        assert dispatch["delivery"].get(args.device_id) is True
        assert command["command"] == "SYNC_PLAY"
        assert command["video_url"] == args.video_url
        assert isinstance(command["timestamp"], (int, float))
        print("dispatch:", json.dumps(dispatch))
        print("device command:", json.dumps(command))
        print("FLEET_WS_TEST_OK")
    finally:
        device.close()
        operator.close()


if __name__ == "__main__":
    main()
```

Run it while FastAPI is running:

```bash
python scripts/fleet_ws_test.py
```

On Windows PowerShell, if the environment has an outbound WebSocket proxy configured, test with
the local host excluded from the proxy first:

```powershell
$env:NO_PROXY = 'localhost,127.0.0.1'
python scripts\fleet_ws_test.py
```

The current WebSocket implementation does not authenticate the handshake; this test validates
the local protocol only. Add the production authentication and authorization described in the
audit before exposing these endpoints beyond a trusted development network.

## Optional automated smoke test

`scripts/smoke_test.py` exercises REST, SRS callbacks, and the WebSocket flow with SQLite. It
sets its own SQLite URL relative to the current working directory. Run it from a disposable
directory with `DEBUG=false` so the development seed does not pre-create `HS-01`:

### macOS/Linux

```bash
REPO_DIR="$PWD"
SMOKE_DIR="$(mktemp -d)"
cd "$SMOKE_DIR"
DEBUG=false PYTHONPATH="$REPO_DIR" python "$REPO_DIR/scripts/smoke_test.py"
```

### Windows PowerShell

```powershell
$repo = (Get-Location).Path
$smokeDir = Join-Path $env:TEMP 'hominsu-smoke-run'
New-Item -ItemType Directory -Force -Path $smokeDir | Out-Null
Push-Location $smokeDir
$env:DEBUG = 'false'
$env:PYTHONPATH = $repo
python "$repo\scripts\smoke_test.py"
Pop-Location
```

Expected final line:

```text
SMOKE_TEST_OK - all 11 checks passed
```

## Troubleshooting

### SRS starts, but publish hooks do not arrive

- Confirm FastAPI is listening on port 8000 before publishing.
- Confirm `host.docker.internal` resolves inside the SRS container:

  ```bash
  docker compose -f docker-compose.local.yml exec srs getent hosts host.docker.internal
  ```

- Inspect `docker compose ... logs srs` and the FastAPI terminal together.
- On Linux, keep the `extra_hosts` entry from `docker-compose.local.yml`.

### HLS remains 404

- Keep the FFmpeg/OBS publisher running; SRS cannot create a playlist without an active stream.
- Confirm the RTMP URL uses exactly `/live/insta-001`.
- Wait for the initial fragments, then inspect SRS logs.
- Confirm port 8080 is not occupied by another process.

### PostgreSQL connection failures

```bash
docker compose -f docker-compose.local.yml ps
docker compose -f docker-compose.local.yml logs postgres
docker compose -f docker-compose.local.yml exec postgres pg_isready -U hominsu -d hominsu
```

Confirm `.env` uses the Compose credentials and `localhost:5432` from the host process:

```dotenv
DATABASE_URL=postgresql+asyncpg://hominsu:hominsu_dev_password@localhost:5432/hominsu
```

### Port conflict

```bash
docker ps --format "table {{.Names}}\t{{.Ports}}"
```

Stop only the named local containers when appropriate:

```bash
docker compose -f docker-compose.local.yml down
```

This removes containers but preserves the named `hominsu_pgdata` volume. Use volume removal only
when intentionally discarding the local database.

## Production readiness checklist

Before deploying this service for real users or paid content:

- [ ] Replace trusted client-side social-login fields with provider token verification.
- [ ] Implement atomic, locked point deductions and idempotent payment/recharge handling.
- [ ] Add content entitlements and idempotent purchases.
- [ ] Authenticate and authorize every fleet REST and WebSocket operation.
- [ ] Add Redis Pub/Sub or a dedicated WebSocket gateway for multi-worker/multi-replica operation.
- [ ] Make reconnect cleanup connection-identity aware; add heartbeat deadlines and command ACKs.
- [ ] Authenticate and strictly validate SRS hooks; reconcile stale live streams.
- [ ] For a deployed environment, run the chosen migration workflow against that environment's PostgreSQL database.
- [ ] Disable `DEBUG`, demo seeding, wildcard CORS, and default secrets.
- [ ] Add database/SRS readiness probes, structured logs, metrics, tracing, and alerting.
- [ ] Put FastAPI, SRS HTTP endpoints, HLS, and WebSockets behind the intended TLS/reverse-proxy policy.
- [ ] Load-test high-bitrate ingest, HLS segment churn, concurrent point deductions, and the target headset count.

## Verification record for this repository

The following checks were run during the audit:

- `python -m compileall -q app scripts` — passed.
- `scripts/smoke_test.py` — passed with `SMOKE_TEST_OK - all 11 checks passed` when run from a clean disposable SQLite working directory with `DEBUG=false`.
- Docker/Compose media verification — not run in the audit environment because the `docker` command was unavailable; execute Steps 1 and 4 on a machine with Docker Engine.
