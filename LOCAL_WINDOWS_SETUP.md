# Local Windows setup

This setup runs FastAPI, PostgreSQL, and SRS on the same Windows computer.
Railway, Vercel, and public URLs are not required.

## Local URLs

```text
FastAPI: http://localhost:8000
Operator WebSocket: ws://localhost:8000/ws/operator
SRS RTMP: rtmp://localhost:1935/live
SRS HLS: http://localhost:8080/live/insta-001.m3u8
Frontend: http://localhost:3000
```

## 1. Start Docker Desktop services

From PowerShell:

```powershell
cd C:\Projects\HOMINSU-BE
docker compose -f docker-compose.local.yml up -d postgres srs
docker ps
```

The SRS container loads `srs.conf`, which sends SRS webhooks to
`host.docker.internal:8000` so Docker can reach FastAPI running on Windows.

## 2. Configure the backend

The local backend `.env` must contain:

```env
DEBUG=true
DATABASE_URL=postgresql+asyncpg://hominsu:hominsu_dev_password@localhost:5432/hominsu
CORS_ORIGINS=["http://localhost:3000"]
SRS_HLS_BASE_URL=http://localhost:8080
```

Start the backend in a separate PowerShell window:

```powershell
cd C:\Projects\HOMINSU-BE
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify:

```powershell
curl.exe http://localhost:8000/health
```

Expected:

```json
{"status":"ok"}
```

## 3. Configure the frontend

`C:\Projects\HOMINSU-FE\.env.local` must contain:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
NEXT_PUBLIC_LIVE_HLS_URL=http://localhost:8080/live/insta-001.m3u8
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

Start the frontend:

```powershell
cd C:\Projects\HOMINSU-FE
npm install
npm run dev
```

Open `http://localhost:3000`.

Restart Next.js after changing `.env.local`; public Next.js variables are read
when the development server starts.

## 4. Configure OBS Studio

If OBS is running on this same Windows computer as Docker and FastAPI:

```text
Server: rtmp://127.0.0.1:1935/live
Stream key: insta-001
```

The complete URL is:

```text
rtmp://127.0.0.1:1935/live/insta-001
```

After starting OBS, verify HLS:

```powershell
curl.exe -i http://localhost:8080/live/insta-001.m3u8
```

The playlist may return `404` until OBS is actively publishing.

## 5. If Insta360 connects directly instead of OBS

`localhost` means the device itself. An Insta360 camera cannot use
`localhost` to reach your Windows computer. Find the Windows LAN address:

```powershell
ipconfig
```

Then use the Windows IPv4 address in the camera:

```text
rtmp://<WINDOWS_LAN_IP>:1935/live/insta-001
```

Allow RTMP through Windows Firewall once, from an elevated PowerShell:

```powershell
New-NetFirewallRule -DisplayName "Hominsu RTMP 1935" -Direction Inbound -Protocol TCP -LocalPort 1935 -Action Allow
```

The camera and Windows computer must be on the same Wi-Fi/LAN. OBS can still
use `127.0.0.1` because OBS runs on the Windows computer.

## 6. Troubleshooting commands

```powershell
docker logs hominsu-srs --tail 100
Test-NetConnection 127.0.0.1 -Port 1935
Test-NetConnection 127.0.0.1 -Port 8080
```

SRS logs should show an RTMP publish after OBS starts. If port `1935` is not
reachable, make sure Docker Desktop is running and the SRS container is up.
