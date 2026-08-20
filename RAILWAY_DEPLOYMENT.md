# Hominsu VR Studio on Railway

For the dashboard click-by-click setup, see
[`RAILWAY_SERVICE_SETUP.md`](RAILWAY_SERVICE_SETUP.md).

This deployment uses two Railway services in the same Railway project and
environment, plus the external Supabase project:

| Railway service | Responsibility | Public exposure |
|---|---|---|
| `Backend` | FastAPI, WebSockets, SRS webhooks | HTTPS domain, normally port `$PORT` |
| `SRS` | RTMP ingest and HLS playback | TCP Proxy for `1935`; HTTPS domain for `8080` |
| Supabase | PostgreSQL database and Supabase project services | Supabase-managed |

Railway does not provide a fixed public Docker IP for this setup. Use the
Railway-provided DNS names and generated TCP Proxy port. Railway supports
HTTP public domains for web traffic and a TCP Proxy for non-HTTP traffic such
as RTMP. See the [Railway TCP Proxy documentation](https://docs.railway.com/networking/tcp-proxy)
and [private networking documentation](https://docs.railway.com/networking/private-networking).

## 1. Important deployment limitation

The current Hominsu SRS configuration provides RTMP and HLS. It does not
configure public SRS WebRTC media. Railway's documented public raw-media path
for this use case is TCP Proxy, so use RTMP ingest plus HLS playback first.
Treat SRS WebRTC/UDP as a separate media-host requirement unless Railway
confirms a compatible public UDP solution for your account and region.

## 2. Push the repository

Commit and push these Railway files with the existing application:

```text
Dockerfile
Dockerfile.srs
srs.railway.conf.template
scripts/start_srs_railway.sh
supabase/migrations/20260820075003_new-migration.sql
railway.backend.toml
railway.srs.toml
```

Do not commit `.env`, passwords, JWT secrets, or database dumps.

## 3. Create the Railway project and services

1. Create an empty Railway project.
2. Add the GitHub repository as a service and name it `Backend`.
3. Add the same repository as another service and name it `SRS`.

Create or use the Supabase project separately. Supabase provides a full
PostgreSQL database. Copy its connection string from the Supabase Connect
panel; `SUPABASE_URL` alone is the HTTP API base URL and cannot be used as
SQLAlchemy's `DATABASE_URL`. Supabase documents the connection modes and
pooler ports in its [database connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres).

Deploy `Backend` first with the Supabase connection string. This gives the SRS
service a resolvable Backend private hostname and port. Deploy SRS next,
create its public HTTP domain and TCP Proxy, and then replace the Backend's
temporary HLS URL with the SRS domain as described below.

Railway treats Compose services as separate Railway services rather than
running a local `docker-compose.yml` unchanged. See the
[Railway Compose deployment guide](https://docs.railway.com/guides/docker-compose).

### Backend service settings

Set the service's Config-as-Code file to:

```text
/railway.backend.toml
```

If your Railway dashboard does not expose a Config-as-Code file selector, set
the equivalent values manually:

```text
Dockerfile: Dockerfile
Healthcheck path: /health
Restart policy: Always
```

### SRS service settings

Set the service's Config-as-Code file to:

```text
/railway.srs.toml
```

If configuring manually:

```text
Dockerfile: Dockerfile.srs
Restart policy: Always
```

## 4. Configure Backend variables

In the `Backend` service Variables tab, add:

```text
DEBUG=false
SECRET_KEY=<long-random-production-secret>
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DATABASE_URL=postgresql+asyncpg://postgres.<PROJECT_REF>:<DB_PASSWORD>@aws-<REGION>.pooler.supabase.com:5432/postgres
SUPABASE_URL=https://<PROJECT_REF>.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_<PUBLIC_KEY>
SUPABASE_SECRET_KEY=sb_secret_<SEALED_SECRET_KEY>
SUPABASE_JWKS_URL=https://<PROJECT_REF>.supabase.co/auth/v1/.well-known/jwks.json
SRS_HLS_BASE_URL=https://placeholder.invalid
CORS_ORIGINS=["https://<your-frontend-domain>"]
```

Use the Supabase **Session pooler** URI for this long-running FastAPI service.
Do not paste the Supabase API URL in `DATABASE_URL`. Set the database password
as a sealed Railway variable. The application converts a standard
`postgresql://` URL to the asyncpg SQLAlchemy scheme automatically.

Use `https://placeholder.invalid` only for the initial Backend deployment if
the SRS public domain has not been generated yet. It is replaced in Section 6
after SRS networking is configured.

If you do not have a frontend yet, use this temporarily for API testing:

```text
CORS_ORIGINS=["*"]
```

Replace it before production browser use.

Apply the Supabase schema from the repository root:

```text
supabase link --project-ref <PROJECT_REF>
supabase db push --linked
```

Verify the remote migration history:

```powershell
supabase migration list --linked
```

It should show the same timestamp in both the `local` and `remote` columns:

```text
20260820075003  20260820075003
```

Run `supabase db push` before deploying the Backend service. The Railway
Backend service does not run Alembic automatically because Supabase CLI is the
schema migration source of truth for this deployment.

These variables are loaded into the backend settings. They do not by
themselves switch the current `/auth/social-login` endpoint to Supabase Auth;
that endpoint currently creates the application's own JWT. Supabase Auth JWT
verification is a separate integration step if you want Supabase to own user
login.

## 5. Configure SRS variables

In the `SRS` service Variables tab, add:

```text
SRS_HOOK_BASE_URL=http://${{Backend.RAILWAY_PRIVATE_DOMAIN}}:${{Backend.PORT}}/api/v1/srs
```

This keeps SRS-to-Backend callbacks on Railway private networking. Railway
documents this reference-variable pattern as
`http://${{api.RAILWAY_PRIVATE_DOMAIN}}:${{api.PORT}}`.

Do not use `localhost` or `host.docker.internal` in the Railway SRS service.
Those names are for the local Docker Desktop setup only.

## 6. Generate the public SRS endpoints

Deploy the `SRS` service once. Then open its Settings → Networking.

### HLS HTTP domain

Generate a public domain for the SRS HTTP server and target internal port:

```text
8080
```

The result will look similar to:

```text
https://srs-production-xxxx.up.railway.app
```

This value is consumed automatically by the Backend variable:

```text
SRS_HLS_BASE_URL=https://${{SRS.RAILWAY_PUBLIC_DOMAIN}}
```

After generating the SRS HTTP domain, replace the temporary Backend variable
with the reference above and redeploy the Backend service.

### RTMP TCP Proxy

Create a TCP Proxy for the SRS internal port:

```text
1935
```

Railway will generate values similar to:

```text
Domain: rtmp-production.proxy.rlwy.net
Port: 15140
```

The generated port is not necessarily `1935`. Use the generated TCP Proxy
port in the Insta360 app.

## 7. Configure Insta360

Use the values displayed by Railway, not the local `192.168.x.x` address:

```text
RTMP URL:   rtmp://<RAILWAY_TCP_PROXY_DOMAIN>:<RAILWAY_TCP_PROXY_PORT>/live
Stream key: insta-001
```

If Insta360 provides one complete Streaming Address field:

```text
rtmp://<RAILWAY_TCP_PROXY_DOMAIN>:<RAILWAY_TCP_PROXY_PORT>/live/insta-001
```

Example only:

```text
rtmp://rtmp-production.proxy.rlwy.net:15140/live/insta-001
```

Do not copy the example domain or port into production. Use the values shown
in your SRS service's TCP Proxy settings.

The public HLS URL after a successful publish is:

```text
https://<SRS_RAILWAY_PUBLIC_DOMAIN>/live/insta-001.m3u8
```

## 8. Create the live content record

Before publishing, create a content record whose `stream_key` exactly matches
the camera key:

```json
{
  "title": "Hominsu Live 360",
  "type": "LIVE_360",
  "stream_key": "insta-001",
  "price_points": 0
}
```

The SRS webhook marks this record live and stores the generated HLS URL. The
webhook still returns `{"code": 0}` for an unknown key, but no content row
will be marked live in that case.

## 9. Verify the deployment

Backend health:

```powershell
curl.exe -i https://<BACKEND_RAILWAY_PUBLIC_DOMAIN>/health
```

Expected response:

```json
{"status":"ok","app":"Hominsu VR Studio API","version":"0.1.0"}
```

After starting Insta360, inspect the SRS service logs. Then request:

```powershell
curl.exe -i https://<SRS_RAILWAY_PUBLIC_DOMAIN>/live/insta-001.m3u8
```

The response should contain `#EXTM3U`. A `404` before the camera publishes is
normal because the HLS playlist does not exist until SRS receives media.

Also verify the backend deployment logs contain a successful callback similar
to:

```text
POST /api/v1/srs/on_publish 200
```

## 10. Railway troubleshooting

### SRS deployment restarts immediately

Check that the SRS Variables tab contains:

```text
SRS_HOOK_BASE_URL=http://${{Backend.RAILWAY_PRIVATE_DOMAIN}}:${{Backend.PORT}}/api/v1/srs
```

The entrypoint intentionally exits if this variable is missing.

### Insta360 remains “Connecting”

Check all of the following:

- The TCP Proxy is configured for internal port `1935`.
- The camera uses the generated TCP Proxy domain and generated port.
- The URL starts with `rtmp://`, not `http://` or `https://`.
- The path is `/live/insta-001`.
- The SRS deployment logs show an RTMP client connection.
- The camera is not still configured with the local `192.168.219.53` address.

### HLS returns 404

Check the SRS logs and confirm an actual RTMP publish exists. The HLS URL is
not available before the first successful publish. Also ensure the Backend
uses the SRS public HTTPS domain in `SRS_HLS_BASE_URL`.

### Backend fails during startup

Check that `DATABASE_URL` is the Supabase Connect **Session pooler** PostgreSQL
URI and that its password is correct. The Supabase CLI migration creates the
schema before the Backend service starts. Local development retains
`create_all()` when `DEBUG=true`.

## Railway variable summary

| Service | Variable | Value |
|---|---|---|
| Backend | `DATABASE_URL` | Supabase Session pooler URI |
| Backend | `SUPABASE_URL` | `https://<PROJECT_REF>.supabase.co` |
| Backend | `SUPABASE_PUBLISHABLE_KEY` | Supabase publishable key |
| Backend | `SUPABASE_SECRET_KEY` | sealed Supabase secret key |
| Backend | `SUPABASE_JWKS_URL` | Supabase Auth JWKS URL |
| Backend | `SRS_HLS_BASE_URL` | `https://${{SRS.RAILWAY_PUBLIC_DOMAIN}}` |
| Backend | `DEBUG` | `false` |
| Backend | `SECRET_KEY` | generated secret |
| SRS | `SRS_HOOK_BASE_URL` | `http://${{Backend.RAILWAY_PRIVATE_DOMAIN}}:${{Backend.PORT}}/api/v1/srs` |
| SRS | TCP Proxy application port | `1935` |
| SRS | HLS public target port | `8080` |
