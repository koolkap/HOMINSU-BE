# HOMINSU Backend

Flask API for HOMINSU's VR catalog, wallets, content access, live streams, and venue device operations.

## Ubuntu setup

The application requires Python 3.12 and PostgreSQL. The commands below install
PostgreSQL directly on Ubuntu; Docker is not required.

### 1. Install system packages

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib python3 python3-venv python3-pip libpq-dev
sudo systemctl enable --now postgresql
sudo systemctl status postgresql --no-pager
```

### 2. Create the PostgreSQL role and database

Open the PostgreSQL shell as its system administrator:

```bash
sudo -u postgres psql
```

Run the following SQL:

```sql
CREATE USER hominsu WITH PASSWORD 'hominsu_dev_password';
CREATE DATABASE hominsu OWNER hominsu;
GRANT ALL PRIVILEGES ON DATABASE hominsu TO hominsu;
\q
```

These credentials are for local development only. Use a strong secret supplied
through environment variables in staging and production.

Verify that the new account can connect:

```bash
PGPASSWORD=hominsu_dev_password psql -h localhost -U hominsu -d hominsu -c 'SELECT current_database(), current_user;'
```

### 3. Configure and install the API

From the backend repository:

```bash
cd /path/to/HOMINSU-BE
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

The development database URL in `.env.example` is:

```text
postgresql+psycopg://hominsu:hominsu_dev_password@localhost:5432/hominsu
```

Change `JWT_SECRET_KEY` in `.env` to a long random value before running the API.
For example:

```bash
sed -i "s|replace-with-a-long-random-development-secret|$(openssl rand -hex 32)|" .env
```

### 4. Apply migrations and seed data

```bash
source .venv/bin/activate
flask db upgrade
flask seed
```

The seed command creates demonstration content, point packages, devices, and the
local accounts listed below.

### 5. Start the API

```bash
source .venv/bin/activate
flask run --debug --host 0.0.0.0 --port 5000
```

Verify the service from another terminal:

```bash
curl http://localhost:5000/health
```

Expected response:

```json
{"data":{"status":"ok"}}
```

If PostgreSQL is not running, inspect it with:

```bash
sudo systemctl status postgresql --no-pager
sudo journalctl -u postgresql --since "10 minutes ago"
```

Development credentials:

| Role | Email | Password |
| --- | --- | --- |
| Member | `member@hominsu.local` | `member1234` |
| Operator | `operator@hominsu.local` | `operator1234` |
| Admin | `admin@hominsu.local` | `admin1234` |

These credentials and secrets are for local development only.

## Commands

```bash
source .venv/bin/activate
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
