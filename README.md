# HOMINSU Backend

Flask API for HOMINSU's VR catalog, wallets, content access, live streams, and venue device operations.

## Setup

Requires Python 3.12 and Docker.

```powershell
Copy-Item .env.example .env
docker compose up -d
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
flask db upgrade
flask seed
flask run --debug
```

If no migration is available during development, initialize an empty database with `flask shell` and `db.create_all()`. Normal environments should use `flask db upgrade`.

Development credentials:

| Role | Email | Password |
| --- | --- | --- |
| Member | `member@hominsu.local` | `member1234` |
| Operator | `operator@hominsu.local` | `operator1234` |
| Admin | `admin@hominsu.local` | `admin1234` |

These credentials and secrets are for local development only.

## Commands

```powershell
flask db upgrade
flask seed
pytest
```

## API

All JSON responses use `{ "data": ... }` or `{ "error": { "code": "...", "message": "..." } }`. Send JWTs as `Authorization: Bearer <token>`.

| Method | Path | Access |
| --- | --- | --- |
| GET | `/health` | Public |
| POST | `/api/v1/auth/login` | Public |
| GET | `/api/v1/catalog/categories` | Public |
| GET | `/api/v1/content?category=&feed=&q=` | Public |
| GET | `/api/v1/content/<id>` | Public |
| GET | `/api/v1/live` | Public |
| GET | `/api/v1/me` | JWT |
| GET | `/api/v1/wallet` | JWT |
| GET | `/api/v1/wallet/packages` | Public |
| POST | `/api/v1/wallet/topups` | JWT |
| POST | `/api/v1/content/<id>/unlock` | JWT |
| GET | `/api/v1/operator/devices` | Operator/Admin |
| POST | `/api/v1/operator/devices/actions` | Operator/Admin |
| POST | `/api/v1/operator/sync` | Operator/Admin |
