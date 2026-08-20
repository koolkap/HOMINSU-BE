# Railway service setup for Hominsu RTMP

Railway must run this repository as **two services**. A single FastAPI
service cannot receive RTMP because the Backend container only runs Uvicorn;
SRS must run in its own container and own port `1935`.

## Service 1: Backend

Keep your existing Backend service for FastAPI.

In Railway, open the Backend service and set:

```text
Dockerfile path: Dockerfile
Public HTTP target port: 8080 (or the port shown by Railway)
Healthcheck path: /health
```

Backend variables:

```env
DEBUG=false
CORS_ORIGINS=["https://hominsu-fe.vercel.app","http://localhost:3000"]
DATABASE_URL=<Supabase session-pooler connection string>
SRS_HLS_BASE_URL=https://<SRS_PUBLIC_HTTP_DOMAIN>
```

The Backend public domain is used only for REST and WebSocket traffic:

```text
https://hominsu-be-production.up.railway.app
wss://hominsu-be-production.up.railway.app/ws/operator
```

It is not an RTMP server.

## Service 2: SRS

Create the second service from the same repository:

1. Open the Railway project.
2. Click **New** or **+ New**.
3. Choose **GitHub Repo** and select this same repository.
4. Name the service `SRS`.
5. Open `SRS → Settings → Build`.
6. Set the Dockerfile path to:

```text
Dockerfile.srs
```

Do not use `Dockerfile` for this service.

Add this SRS variable. Replace the hostname and port with the Backend
service's private hostname and internal HTTP port shown in Railway:

```env
SRS_HOOK_BASE_URL=http://hominsu-be.railway.internal:8080/api/v1/srs
```

The SRS startup script exits immediately if `SRS_HOOK_BASE_URL` is missing.

## SRS networking

Open `SRS → Settings → Networking`.

### HLS HTTP domain

Create a public domain targeting internal port:

```text
8080
```

Copy the generated domain, for example:

```text
https://srs-production-xxxx.up.railway.app
```

Set the Backend variable to that domain:

```env
SRS_HLS_BASE_URL=https://srs-production-xxxx.up.railway.app
```

### RTMP TCP proxy

Create a **TCP Proxy** on the SRS service targeting:

```text
1935
```

Railway generates a hostname and external port, for example:

```text
roundhouse.proxy.rlwy.net:37420
```

The generated proxy must be created on `SRS`, not on `Backend`.

## OBS configuration

Use the TCP proxy generated on the SRS service:

```text
Server: rtmp://roundhouse.proxy.rlwy.net:37420/live
Stream key: insta-001
```

If OBS asks for one complete URL:

```text
rtmp://roundhouse.proxy.rlwy.net:37420/live/insta-001
```

If Railway generates a different proxy hostname or port, use those values.
The external port will not normally be `1935`.

## Vercel variables

In Vercel, set these variables for the Production environment:

```env
NEXT_PUBLIC_API_URL=https://hominsu-be-production.up.railway.app
NEXT_PUBLIC_WS_URL=wss://hominsu-be-production.up.railway.app
NEXT_PUBLIC_LIVE_HLS_URL=https://srs-production-xxxx.up.railway.app/live/insta-001.m3u8
```

Replace `srs-production-xxxx.up.railway.app` with the SRS HTTP domain.
Redeploy Vercel after saving the variables.

## Verification order

1. Backend:

   ```powershell
   curl.exe https://hominsu-be-production.up.railway.app/health
   ```

   Expected response:

   ```json
   {"status":"ok"}
   ```

2. SRS: open the SRS public HTTP domain in a browser. It should respond from
   SRS; it should not show the FastAPI `/health` JSON.

3. Start OBS with the SRS TCP proxy. SRS logs should show an RTMP publish.

4. After OBS starts, request:

   ```powershell
   curl.exe -i https://srs-production-xxxx.up.railway.app/live/insta-001.m3u8
   ```

5. The Backend logs should show the SRS `on_publish` webhook.

If the TCP proxy is reachable but OBS reports **Failed to stream**, the proxy
is usually attached to the Backend service or the SRS service is restarting.
Check that the SRS service uses `Dockerfile.srs` and that
`SRS_HOOK_BASE_URL` is present.
