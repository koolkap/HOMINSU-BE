# Insta360 LAN Streaming Setup

This guide connects an Insta360 app on the same Wi-Fi/LAN as the Hominsu computer to the
existing SRS + FastAPI backend.

The important distinction is:

- `localhost` means “this same device.” It will not work from the Insta360 phone/app.
- The Insta360 app must use the private IPv4 address of the computer running Docker/SRS.
- Nginx is optional. SRS already accepts RTMP on port `1935` and serves HLS on port `8080`.
- The script in `scripts/setup_lan_network.py` changes external URLs only. It does not replace
  PostgreSQL’s `localhost` or SRS’s Docker callback address.

## 1. Network requirements

The phone running Insta360 and the computer running Hominsu must be on the same network.

- Prefer the same Wi-Fi access point or the same wired LAN.
- Do not use a VPN address, Docker bridge address, `127.0.0.1`, or an `169.254.x.x` address.
- Guest Wi-Fi may block device-to-device traffic; use the normal/private network if possible.
- Windows Firewall must allow inbound TCP ports `1935`, `8000`, and `8080` from the private network.
  If Nginx is enabled, also allow its port, `8088` by default.

## 2. Find the correct host IP

On the computer running SRS, open PowerShell and run:

```powershell
ipconfig
```

Find the active **Wi-Fi** or **Ethernet** adapter and copy its **IPv4 Address**, for example:

```text
Wireless LAN adapter Wi-Fi:
   IPv4 Address. . . . . . . . . . . : 192.168.1.25
```

Use `192.168.1.25` below only as an example. Your address may be `192.168.0.x`, `10.x.x.x`, or
another private LAN range.

The Python helper can detect candidates automatically:

```powershell
python scripts\setup_lan_network.py --list
python scripts\setup_lan_network.py --ip 192.168.1.25
```

If more than one address is found, always pass the address belonging to the same Wi-Fi/LAN as
the phone:

```powershell
python scripts\setup_lan_network.py --ip 192.168.1.25
```

The default command is a dry run. It prints the URLs but does not change files.

## 3. Configure LAN URLs and generate Nginx configuration

From the repository root, with the project virtual environment active, run:

```powershell
python scripts\setup_lan_network.py --ip 192.168.1.25 --apply
```

This performs the following actions:

1. Backs up the current `.env` as `.env.lan.backup` when `.env` exists.
2. Sets `SRS_HLS_BASE_URL` to `http://192.168.1.25:8088` because Nginx is enabled by default.
3. Sets local CORS origins for `http://192.168.1.25:3000` and `http://localhost:3000`.
4. Writes `LAN_HOST_IP=192.168.1.25` to `.env` for reference.
5. Generates `nginx.local.conf` for FastAPI REST, FastAPI WebSockets, and SRS HLS.

The script intentionally leaves these values unchanged:

```dotenv
DATABASE_URL=postgresql+asyncpg://hominsu:hominsu_dev_password@localhost:5432/hominsu
```

PostgreSQL is reached by FastAPI on the same computer, so `localhost` is correct there. It also
leaves this SRS hook unchanged:

```text
http://host.docker.internal:8000/api/v1/srs/on_publish
```

SRS is running inside Docker, so `host.docker.internal` is the correct Docker-to-host address in
the existing Compose setup. Do not replace it with the phone’s IP.

### Use SRS directly without Nginx

Nginx is not needed for Insta360 ingest. To keep HLS URLs on SRS port `8080`, run:

```powershell
python scripts\setup_lan_network.py `
  --ip 192.168.1.25 `
  --no-nginx-urls `
  --apply
```

Use this direct HLS URL:

```text
http://192.168.1.25:8080/live/insta-001.m3u8
```

The RTMP URL remains the same in both modes:

```text
rtmp://192.168.1.25:1935/live/insta-001
```

## 4. Start the local services

Start PostgreSQL and SRS from the repository root:

```powershell
docker compose -f docker-compose.local.yml up -d postgres srs
docker compose -f docker-compose.local.yml ps
```

Start FastAPI in another terminal:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The `0.0.0.0` bind is required. If FastAPI binds only to `127.0.0.1`, another device cannot
reach the API or WebSockets.

Verify host access first:

```powershell
curl.exe --fail http://192.168.1.25:8000/health
curl.exe --fail http://192.168.1.25:8080/live/insta-001.m3u8
```

The second request can return `404` until a publisher is active; that is expected.

## 5. Install and start Nginx (optional)

Nginx is used here as an HTTP reverse proxy for one stable LAN address. It does not ingest RTMP;
SRS continues to own port `1935`.

Install Nginx separately and make `nginx.exe` available on `PATH`. For example, download the
official Windows zip from <https://nginx.org/en/download.html>, extract it to a directory such as
`C:\nginx`, and either add that directory to `PATH` or pass the executable location manually.

Validate the generated config from the repository root:

```powershell
nginx.exe -t -p "${PWD}\" -c "${PWD}\nginx.local.conf"
```

Start it:

```powershell
nginx.exe -p "${PWD}\" -c "${PWD}\nginx.local.conf"
```

Or let the helper validate and start Nginx after generating the config:

```powershell
python scripts\setup_lan_network.py `
  --ip 192.168.1.25 `
  --apply `
  --start-nginx
```

With the default Nginx port, the externally reachable URLs are:

```text
RTMP ingest:        rtmp://192.168.1.25:1935/live/insta-001
HLS playback:       http://192.168.1.25:8088/live/insta-001.m3u8
FastAPI base:       http://192.168.1.25:8088
Operator WebSocket: ws://192.168.1.25:8088/ws/operator
```

Stop Nginx with:

```powershell
nginx.exe -s quit -p "${PWD}\" -c "${PWD}\nginx.local.conf"
```

If port `8088` is occupied, choose another port consistently:

```powershell
python scripts\setup_lan_network.py --ip 192.168.1.25 --nginx-port 8090 --apply
```

## 6. Configure the Insta360 app

In the Insta360 app’s live-stream/RTMP settings, select a custom RTMP destination and use:

```text
Server/URL: rtmp://192.168.1.25:1935/live
Stream key: insta-001
```

Some clients require the complete URL in one field:

```text
rtmp://192.168.1.25:1935/live/insta-001
```

Create a matching content record before publishing so the SRS webhook can mark it live:

```powershell
$login = Invoke-RestMethod -Method Post `
  -Uri http://192.168.1.25:8000/api/v1/auth/social-login `
  -ContentType 'application/json' `
  -Body '{"email":"lan-test@example.com","name":"LAN Test","provider":"local"}'

$headers = @{ Authorization = "Bearer $($login.access_token)" }
Invoke-RestMethod -Method Post `
  -Uri http://192.168.1.25:8000/api/v1/contents `
  -Headers $headers `
  -ContentType 'application/json' `
  -Body '{"title":"Insta360 LAN Test","type":"LIVE_360","stream_key":"insta-001","price_points":0}'
```

## 7. Verify the stream

Start publishing in the Insta360 app, wait 5–10 seconds for HLS segments, then check:

```powershell
curl.exe --fail --show-error http://192.168.1.25:8080/live/insta-001.m3u8
```

If Nginx is enabled, check the proxy URL instead:

```powershell
curl.exe --fail --show-error http://192.168.1.25:8088/live/insta-001.m3u8
```

Check backend live state:

```powershell
curl.exe --fail --show-error "http://192.168.1.25:8000/api/v1/contents?live_only=true"
```

Expected behavior:

1. SRS accepts the RTMP publisher on port `1935`.
2. SRS creates `/live/insta-001.m3u8` on port `8080`.
3. SRS calls FastAPI `on_publish` through `host.docker.internal`.
4. FastAPI marks the matching content `is_live: true`.
5. HLS can be opened from a browser/player on the LAN using the host IP.
6. Stopping the Insta360 stream triggers `on_unpublish` and marks the content offline.

## 8. Windows Firewall

If the API works on the host but not from the phone, add private-network inbound rules in an
elevated PowerShell window:

```powershell
New-NetFirewallRule -DisplayName 'Hominsu RTMP 1935' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 1935 -Profile Private
New-NetFirewallRule -DisplayName 'Hominsu FastAPI 8000' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 -Profile Private
New-NetFirewallRule -DisplayName 'Hominsu HLS 8080' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8080 -Profile Private
New-NetFirewallRule -DisplayName 'Hominsu Nginx 8088' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8088 -Profile Private
```

Only create the Nginx rule if Nginx is enabled. Do not expose PostgreSQL port `5432` to the LAN
unless there is a specific administrative requirement.

## 9. Troubleshooting

### The Insta360 app cannot connect

- Confirm the phone and computer are on the same private Wi-Fi/LAN.
- Confirm the URL uses the computer’s Wi-Fi/Ethernet IPv4 address, not `localhost`.
- Confirm the RTMP port is `1935`, not `8000`, `8080`, or `8088`.
- Confirm Docker is publishing SRS: `docker compose -f docker-compose.local.yml ps`.
- Check Windows Firewall and router/client-isolation settings.
- Run `python scripts/setup_lan_network.py --list` and select the correct adapter with `--ip`.

### HLS is 404

- Keep the Insta360 publisher running; SRS does not create a playlist before an active stream.
- Check the stream key spelling: `insta-001` is case-sensitive.
- Wait for the first fragments.
- Inspect SRS logs:

  ```powershell
  docker compose -f docker-compose.local.yml logs -f srs
  ```

### The stream works on the host but not on another device

- Use the LAN IP in the player URL.
- Test `http://192.168.1.25:8080/` from the phone browser.
- Check the private-network firewall rule.
- If using Nginx, test port `8088` and verify `nginx.exe -t` succeeds.

### SRS does not mark content live

- Confirm the content row has `stream_key: "insta-001"`.
- Keep `host.docker.internal` in `srs.conf` for the current Docker Desktop/Compose setup.
- Confirm FastAPI is running before the first publish.
- Inspect both FastAPI and SRS logs.

## Important security note

This LAN setup is for trusted local development. The current WebSocket and SRS webhook routes are
not fully authenticated, and the social-login route trusts client-supplied identity fields. Do not
port-forward RTMP, HLS, FastAPI, or Nginx directly to the public Internet. Before production, add
TLS/reverse-proxy policy, authenticated WebSockets, signed SRS webhooks, verified social tokens,
rate limiting, and the concurrency fixes documented in `EXECUTION.md`.

