# HOMINSU Backend

Flask API for HOMINSU's VR catalog, wallets, content access, live streams, and venue device operations.

## Setup

The application requires Python 3.12 and PostgreSQL. PostgreSQL runs directly on
the host operating system; Docker is not required. Uvicorn serves the Flask API
through the ASGI adapter defined in `asgi.py`.

### Ubuntu

#### 1. Install system packages

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib python3 python3-venv python3-pip libpq-dev
sudo systemctl enable --now postgresql
sudo systemctl status postgresql --no-pager
```

#### 2. Create the PostgreSQL role and database

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

#### 3. Configure and install the API

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

#### 4. Apply migrations and seed data

```bash
source .venv/bin/activate
flask db upgrade
flask seed
```

The seed command creates demonstration content, point packages, devices, and the
local accounts listed below.

#### 5. Start the API

For development with automatic reload:

```bash
source .venv/bin/activate
uvicorn asgi:app --host 0.0.0.0 --port 5000 --reload
```

For a server process without the development reloader:

```bash
source .venv/bin/activate
uvicorn asgi:app --host 0.0.0.0 --port 5000 --workers 4
```

Verify the service from another terminal:

```bash
curl http://localhost:5000/
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

### Windows

#### 1. Install Python and PostgreSQL

Install Python 3.12 from [python.org](https://www.python.org/downloads/windows/)
or with Windows Package Manager:

```powershell
winget install --exact --id Python.Python.3.12
```

Install PostgreSQL using the Windows installer from
[postgresql.org](https://www.postgresql.org/download/windows/). During setup:

1. Keep the default port `5432`.
2. Set and retain the password for the built-in `postgres` administrator.
3. Install the PostgreSQL command-line tools.
4. Add the PostgreSQL `bin` directory to `PATH` if the installer does not do so.

The default command-line tools directory is similar to
`C:\Program Files\PostgreSQL\17\bin`. The version number may differ.

Open a new PowerShell window and verify both installations:

```powershell
py -3.12 --version
psql --version
Get-Service postgresql*
```

If `psql` is not in `PATH`, invoke it using its full path, for example:

```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" --version
```

#### 2. Create the PostgreSQL role and database

Connect using the administrator password selected during PostgreSQL setup:

```powershell
psql -U postgres -h localhost
```

Run the following SQL:

```sql
CREATE USER hominsu WITH PASSWORD 'hominsu_dev_password';
CREATE DATABASE hominsu OWNER hominsu;
GRANT ALL PRIVILEGES ON DATABASE hominsu TO hominsu;
\q
```

Verify the application account from PowerShell:

```powershell
$env:PGPASSWORD = "hominsu_dev_password"
psql -h localhost -U hominsu -d hominsu -c "SELECT current_database(), current_user;"
Remove-Item Env:PGPASSWORD
```

#### 3. Configure and install the API

From the backend repository:

```powershell
Set-Location C:\path\to\HOMINSU-BE
Copy-Item .env.example .env
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

The development database URL in `.env` should be:

```text
postgresql+psycopg://hominsu:hominsu_dev_password@localhost:5432/hominsu
```

Open `.env` and replace `JWT_SECRET_KEY` with a long random value:

```powershell
notepad .env
```

#### 4. Apply migrations and seed data

```powershell
.\.venv\Scripts\Activate.ps1
flask db upgrade
flask seed
```

#### 5. Start the API

For development with automatic reload:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn asgi:app --host 0.0.0.0 --port 5000 --reload
```

For a server process without the development reloader:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn asgi:app --host 0.0.0.0 --port 5000 --workers 4
```

Verify the API from another PowerShell window:

```powershell
Invoke-RestMethod http://localhost:5000/
Invoke-RestMethod http://localhost:5000/health
```

If PostgreSQL is not running, inspect and start its Windows service:

```powershell
Get-Service postgresql*
Get-Service postgresql* | Start-Service
```

Development credentials:

| Role | Email | Password |
| --- | --- | --- |
| Member | `member@hominsu.local` | `member1234` |
| Operator | `operator@hominsu.local` | `operator1234` |
| Admin | `admin@hominsu.local` | `admin1234` |

These credentials and secrets are for local development only.

## Commands

Ubuntu:

```bash
source .venv/bin/activate
flask db upgrade
flask seed
pytest
uvicorn asgi:app --host 0.0.0.0 --port 5000 --reload
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
flask db upgrade
flask seed
pytest
uvicorn asgi:app --host 0.0.0.0 --port 5000 --reload
```

Run migrations and seed commands before starting multiple Uvicorn workers. The
workers must not execute migrations automatically. In production, place Uvicorn
behind a reverse proxy such as Nginx or a managed load balancer for TLS and
request-size controls.

After Uvicorn starts, the available entry URLs are:

| URL | Purpose |
| --- | --- |
| `http://localhost:5000/` | API service information |
| `http://localhost:5000/health` | Health check |
| `http://localhost:5000/api/v1` | Versioned API information |
| `http://localhost:5000/api/v1/content` | Public content catalog |
| `http://localhost:5000/docs/` | Interactive Swagger UI |
| `http://localhost:5000/openapi.json` | Raw OpenAPI specification |

A JSON `not_found` response means Uvicorn is reachable but the requested path
does not match a registered API route. Confirm the URL against the API table
below.

## Swagger API testing

Start Uvicorn and open the interactive documentation in a browser:

```text
http://localhost:5000/docs/
```

Swagger displays every API name, HTTP method, path parameter, query parameter,
request body, and example payload. Select an endpoint, select **Try it out**, fill
in the values, and select **Execute** to call the running API.

To test protected account endpoints:

1. Open `POST /api/v1/auth/login`.
2. Select **Try it out** and use `member@hominsu.local` / `member1234`.
3. Copy `data.access_token` from the response without adding quotes.
4. Select **Authorize** at the top of Swagger.
5. Paste the token into the Bearer authorization field and select **Authorize**.

Use `operator@hominsu.local` / `operator1234` when testing endpoints under the
Operator section. Swagger retains the authorization token while the page remains
open. The raw machine-readable specification is available at
`http://localhost:5000/openapi.json`.

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
