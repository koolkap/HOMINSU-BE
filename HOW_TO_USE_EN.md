# HOMINSU Backend: How to Use

This standalone guide covers database setup, API startup, development accounts,
Swagger testing, endpoint usage, maintenance, and troubleshooting on Ubuntu and
Windows.

## 1. Architecture

- Flask provides the REST API and application factory.
- SQLAlchemy stores users, content, wallets, unlocks, venues, and devices.
- PostgreSQL is the target database.
- Alembic/Flask-Migrate manages schema versions.
- Flask-JWT-Extended provides Bearer authentication.
- `asgi.py` wraps the Flask WSGI app with `asgiref.WsgiToAsgi`.
- Uvicorn serves that ASGI wrapper.
- Swagger UI is generated from the OpenAPI specification in `app/openapi.py`.

## 2. Development configuration

The local database values are:

| Setting | Value |
| --- | --- |
| Database | `hominsu` |
| Username | `hominsu` |
| Password | `hominsu_dev_password` |
| Host | `localhost` |
| Port | `5432` |

The SQLAlchemy URL is:

```text
postgresql+psycopg://hominsu:hominsu_dev_password@localhost:5432/hominsu
```

These values are for local development only.

## 3. Ubuntu installation

### Install PostgreSQL and Python

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib python3 python3-venv python3-pip libpq-dev
sudo systemctl enable --now postgresql
```

### Create the role and database

```bash
sudo -u postgres psql
```

Run:

```sql
CREATE USER hominsu WITH PASSWORD 'hominsu_dev_password';
CREATE DATABASE hominsu OWNER hominsu;
GRANT ALL PRIVILEGES ON DATABASE hominsu TO hominsu;
\q
```

Verify the connection:

```bash
PGPASSWORD=hominsu_dev_password psql -h localhost -U hominsu -d hominsu -c 'SELECT current_database(), current_user;'
```

### Install the API

```bash
cd /path/to/HOMINSU-BE
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Generate a local JWT secret:

```bash
sed -i "s|replace-with-a-long-random-development-secret|$(openssl rand -hex 32)|" .env
```

## 4. Windows installation

Install Python 3.12 and PostgreSQL, including PostgreSQL command-line tools.
Verify them from a new PowerShell window:

```powershell
py -3.12 --version
psql --version
Get-Service postgresql*
```

Connect using the administrator password selected in the PostgreSQL installer:

```powershell
psql -U postgres -h localhost
```

Run the same SQL:

```sql
CREATE USER hominsu WITH PASSWORD 'hominsu_dev_password';
CREATE DATABASE hominsu OWNER hominsu;
GRANT ALL PRIVILEGES ON DATABASE hominsu TO hominsu;
\q
```

Install the project:

```powershell
Set-Location C:\path\to\HOMINSU-BE
Copy-Item .env.example .env
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
notepad .env
```

Replace `JWT_SECRET_KEY` in `.env` with a long random secret.

## 5. Environment variables

```dotenv
FLASK_APP=app:create_app
FLASK_ENV=development
DATABASE_URL=postgresql+psycopg://hominsu:hominsu_dev_password@localhost:5432/hominsu
JWT_SECRET_KEY=replace-with-a-long-random-secret
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

Add every allowed frontend origin to `CORS_ORIGINS`, separated by commas. Do not
commit a real `.env` file.

## 6. Initialize the database

Activate the virtual environment, then apply migrations and seed records.

Ubuntu:

```bash
source .venv/bin/activate
flask db upgrade
flask seed
```

Windows:

```powershell
.\.venv\Scripts\Activate.ps1
flask db upgrade
flask seed
```

Run `flask seed` after `flask db upgrade`. The current seed is idempotent once
roles exist and creates users, content, wallet packages, a venue, and headsets.

## 7. Start Uvicorn

Development with automatic reload:

```bash
uvicorn asgi:app --host 0.0.0.0 --port 5000 --reload
```

Multi-worker server process:

```bash
uvicorn asgi:app --host 0.0.0.0 --port 5000 --workers 4
```

Run migrations once before starting multiple workers. Do not run schema changes
from each worker. In production, place Uvicorn behind Nginx or a managed load
balancer for TLS, request limits, and trusted proxy handling.

## 8. Service URLs

| URL | Purpose |
| --- | --- |
| `http://localhost:5000/` | Service information |
| `http://localhost:5000/health` | Health response |
| `http://localhost:5000/api/v1` | Versioned API information |
| `http://localhost:5000/docs/` | Interactive Swagger UI |
| `http://localhost:5000/openapi.json` | Raw OpenAPI specification |

Check startup:

```bash
curl http://localhost:5000/health
```

Expected result:

```json
{"data":{"status":"ok"}}
```

## 9. Seed login accounts

| Role | Email | Password | Access |
| --- | --- | --- | --- |
| Member | `member@hominsu.local` | `member1234` | Account, wallet, top-up, unlock |
| Operator | `operator@hominsu.local` | `operator1234` | Member APIs plus operator APIs |
| Admin | `admin@hominsu.local` | `admin1234` | Operator-protected APIs |

Replace all seed credentials for any shared or production deployment.

## 10. Test with Swagger

1. Open `http://localhost:5000/docs/`.
2. Expand `POST /api/v1/auth/login`.
3. Select **Try it out**.
4. Submit a development email and password.
5. Copy `data.access_token` from the response.
6. Select **Authorize** at the top of Swagger.
7. Paste only the token; Swagger adds the `Bearer` prefix.
8. Execute protected Account endpoints.
9. Log in with the operator account and authorize again before testing Operator
   endpoints.

## 11. Endpoint reference

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/` | Public | Service metadata |
| GET | `/health` | Public | Health check |
| GET | `/openapi.json` | Public | OpenAPI specification |
| GET | `/docs/` | Public | Swagger UI |
| POST | `/api/v1/auth/login` | Public | Create JWT access token |
| GET | `/api/v1/catalog/categories` | Public | List categories |
| GET | `/api/v1/content` | Public | Search/filter published content |
| GET | `/api/v1/content/<id>` | Public | Content details |
| GET | `/api/v1/live` | Public | Live and scheduled streams |
| GET | `/api/v1/me` | JWT | Current user profile |
| GET | `/api/v1/wallet` | JWT | Current wallet balances |
| GET | `/api/v1/wallet/packages` | Public | Point packages |
| POST | `/api/v1/wallet/topups` | JWT | Credit a package using a unique reference |
| POST | `/api/v1/content/<id>/unlock` | JWT | Unlock via ad, points, or cash |
| GET | `/api/v1/operator/devices` | Operator/Admin | List venue headsets |
| POST | `/api/v1/operator/devices/actions` | Operator/Admin | Queue bulk device actions |
| POST | `/api/v1/operator/sync` | Operator/Admin | Create fleet sync records |

## 12. Request examples

### Login

```bash
curl -X POST http://localhost:5000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"member@hominsu.local","password":"member1234"}'
```

Save the returned token on Ubuntu:

```bash
TOKEN='paste-access-token-here'
```

In PowerShell:

```powershell
$token = "paste-access-token-here"
```

### Filter content

```bash
curl 'http://localhost:5000/api/v1/content?category=culture&feed=featured&q=경복궁'
```

Valid `feed` values are `latest`, `featured`, and `free`.

### Current user and wallet

```bash
curl http://localhost:5000/api/v1/me -H "Authorization: Bearer $TOKEN"
curl http://localhost:5000/api/v1/wallet -H "Authorization: Bearer $TOKEN"
```

### Unlock content

```bash
curl -X POST http://localhost:5000/api/v1/content/1/unlock \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"method":"points"}'
```

`method` accepts `ad`, `points`, or `cash`. Unlocking is idempotent per user and
content. Repeating it returns the existing unlock instead of charging again.

### Top up points

```bash
curl -X POST http://localhost:5000/api/v1/wallet/topups \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"package_id":1,"reference":"manual-test-001"}'
```

Every successful top-up requires a unique `reference`. This development endpoint
assumes payment was completed; production must verify a payment provider webhook.

### Queue a bulk device action

Use an operator token:

```bash
curl -X POST http://localhost:5000/api/v1/operator/devices/actions \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"device_ids":[1,2],"action":"reboot","payload":{}}'
```

Actions: `launch_content`, `stop_content`, `wake`, `sleep`, `reboot`, `update`,
and `refresh_catalog`.

### Synchronize headsets

```bash
curl -X POST http://localhost:5000/api/v1/operator/sync \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"device_ids":[1,2],"payload":{"content_id":1,"position_seconds":0}}'
```

The API stores commands and sync records. A real device transport such as MQTT,
WebSocket, or a headset agent is not included yet.

## 13. Response format and common statuses

Successful responses use:

```json
{"data": {}}
```

Errors use:

```json
{"error":{"code":"validation_error","message":"Description"}}
```

| Status | Meaning |
| --- | --- |
| `200` | Successful read or idempotent result |
| `201` | Resource/transaction created |
| `400` | Invalid request data |
| `401` | Missing, invalid, or expired JWT |
| `403` | Authenticated account lacks operator role |
| `404` | Route or resource does not exist |
| `409` | Insufficient funds or duplicate payment reference |
| `422` | Invalid JWT format |

## 14. Development and maintenance commands

```bash
pytest
flask db current
flask db upgrade
flask seed
```

When changing models, create and review a migration before applying it:

```bash
flask db migrate -m "describe schema change"
flask db upgrade
```

Never edit an already deployed migration to represent a new production change.

## 15. Troubleshooting

| Problem | Resolution |
| --- | --- |
| Root URL returned `not_found` | Update to the latest code; `/` is now registered |
| Swagger is missing | Run `pip install -r requirements.txt`, restart Uvicorn, open `/docs/` |
| `psql` cannot connect | Check PostgreSQL service, port, role, password, and `DATABASE_URL` |
| `relation does not exist` | Run `flask db upgrade` |
| No demo records/accounts | Run `flask seed` after migrations |
| `401` in Swagger | Log in, copy the new token, and use **Authorize** |
| `403` for device APIs | Use the operator or admin token |
| `404` JSON | Uvicorn is reachable, but the requested route is wrong |
| Browser CORS failure | Add the exact frontend origin to `CORS_ORIGINS` and restart |
| Duplicate top-up reference | Send a new unique `reference` |
| Port 5000 already used | Stop the other service or choose `--port 5001` and update frontend URL |

Ubuntu service checks:

```bash
sudo systemctl status postgresql --no-pager
sudo journalctl -u postgresql --since "10 minutes ago"
```

Windows service checks:

```powershell
Get-Service postgresql*
Get-Service postgresql* | Start-Service
```

## 16. Production checklist

- Replace database, JWT, seed, and account credentials.
- Disable debug/reload mode.
- Use managed PostgreSQL backups and least-privilege access.
- Run migrations as a controlled release step.
- Put Uvicorn behind HTTPS and a reverse proxy/load balancer.
- Restrict CORS to deployed frontend origins.
- Add payment-provider verification before enabling top-ups or cash purchases.
- Add token revocation/refresh policy, rate limiting, audit logging, monitoring,
  and secret management.
- Connect operator records to an authenticated device-command transport.
