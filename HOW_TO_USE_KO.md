# HOMINSU 백엔드 사용 안내서

이 문서는 Ubuntu와 Windows에서 PostgreSQL과 API를 설치하고 실행하는 방법,
개발용 계정, Swagger 테스트, API 요청, 운영 명령 및 문제 해결 절차를 설명합니다.

## 1. 구성 구조

- Flask가 REST API와 애플리케이션 팩토리를 제공합니다.
- SQLAlchemy가 사용자, 콘텐츠, 지갑, 잠금 해제, 체험장 및 디바이스를 저장합니다.
- 운영 대상 데이터베이스는 PostgreSQL입니다.
- Alembic/Flask-Migrate가 DB 스키마 버전을 관리합니다.
- Flask-JWT-Extended가 Bearer 인증을 처리합니다.
- `asgi.py`가 Flask WSGI 앱을 `asgiref.WsgiToAsgi`로 감쌉니다.
- Uvicorn이 ASGI 래퍼를 실행합니다.
- `app/openapi.py`의 명세를 Swagger UI로 제공합니다.

## 2. 개발용 데이터베이스 설정

| 항목 | 값 |
| --- | --- |
| 데이터베이스 | `hominsu` |
| 사용자 | `hominsu` |
| 비밀번호 | `hominsu_dev_password` |
| 호스트 | `localhost` |
| 포트 | `5432` |

SQLAlchemy 연결 주소:

```text
postgresql+psycopg://hominsu:hominsu_dev_password@localhost:5432/hominsu
```

위 정보는 로컬 개발 전용입니다.

## 3. Ubuntu 설치

### PostgreSQL 및 Python 설치

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib python3 python3-venv python3-pip libpq-dev
sudo systemctl enable --now postgresql
```

### 사용자와 데이터베이스 생성

```bash
sudo -u postgres psql
```

다음 SQL을 실행합니다.

```sql
CREATE USER hominsu WITH PASSWORD 'hominsu_dev_password';
CREATE DATABASE hominsu OWNER hominsu;
GRANT ALL PRIVILEGES ON DATABASE hominsu TO hominsu;
\q
```

연결을 확인합니다.

```bash
PGPASSWORD=hominsu_dev_password psql -h localhost -U hominsu -d hominsu -c 'SELECT current_database(), current_user;'
```

### API 설치

```bash
cd /path/to/HOMINSU-BE
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
sed -i "s|replace-with-a-long-random-development-secret|$(openssl rand -hex 32)|" .env
```

## 4. Windows 설치

Python 3.12와 PostgreSQL 명령줄 도구를 포함하여 설치합니다. 새 PowerShell
창에서 확인합니다.

```powershell
py -3.12 --version
psql --version
Get-Service postgresql*
```

PostgreSQL 설치 시 지정한 관리자 비밀번호로 접속합니다.

```powershell
psql -U postgres -h localhost
```

다음 SQL을 실행합니다.

```sql
CREATE USER hominsu WITH PASSWORD 'hominsu_dev_password';
CREATE DATABASE hominsu OWNER hominsu;
GRANT ALL PRIVILEGES ON DATABASE hominsu TO hominsu;
\q
```

프로젝트를 설치합니다.

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

`.env`의 `JWT_SECRET_KEY`를 충분히 긴 임의 문자열로 변경합니다.

## 5. 환경 변수

```dotenv
FLASK_APP=app:create_app
FLASK_ENV=development
DATABASE_URL=postgresql+psycopg://hominsu:hominsu_dev_password@localhost:5432/hominsu
JWT_SECRET_KEY=충분히-긴-임의-비밀키로-변경
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

허용할 프런트엔드 주소를 `CORS_ORIGINS`에 쉼표로 구분하여 추가합니다. 실제
비밀값이 들어 있는 `.env` 파일은 Git에 커밋하지 않습니다.

## 6. DB 초기화

가상 환경을 활성화한 뒤 마이그레이션과 시드 명령을 순서대로 실행합니다.

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

`flask seed`는 역할이 이미 존재하면 중복 생성하지 않습니다. 개발용 사용자,
콘텐츠, 포인트 상품, 체험장 및 헤드셋을 생성합니다.

## 7. Uvicorn 실행

자동 재시작이 필요한 개발 환경:

```bash
uvicorn asgi:app --host 0.0.0.0 --port 5000 --reload
```

여러 워커를 사용하는 서버 프로세스:

```bash
uvicorn asgi:app --host 0.0.0.0 --port 5000 --workers 4
```

여러 워커를 실행하기 전에 마이그레이션을 한 번만 수행합니다. 운영 환경에서는
Uvicorn 앞에 Nginx 또는 관리형 로드 밸런서를 두어 TLS, 요청 크기 및 프록시
설정을 관리합니다.

## 8. 접속 주소

| 주소 | 기능 |
| --- | --- |
| `http://localhost:5000/` | 서비스 정보 |
| `http://localhost:5000/health` | 상태 확인 |
| `http://localhost:5000/api/v1` | API 버전 정보 |
| `http://localhost:5000/docs/` | Swagger UI |
| `http://localhost:5000/openapi.json` | OpenAPI 원본 명세 |

실행 상태를 확인합니다.

```bash
curl http://localhost:5000/health
```

정상 응답:

```json
{"data":{"status":"ok"}}
```

## 9. 개발용 로그인 계정

| 역할 | 이메일 | 비밀번호 | 권한 |
| --- | --- | --- | --- |
| 일반 회원 | `member@hominsu.local` | `member1234` | 계정, 지갑, 충전, 잠금 해제 |
| 운영자 | `operator@hominsu.local` | `operator1234` | 회원 API와 운영자 API |
| 관리자 | `admin@hominsu.local` | `admin1234` | 운영자 보호 API |

공유 서버나 운영 환경에서는 모든 시드 계정과 비밀번호를 교체하십시오.

## 10. Swagger 테스트 방법

1. `http://localhost:5000/docs/`를 엽니다.
2. `POST /api/v1/auth/login`을 펼칩니다.
3. **Try it out**을 누릅니다.
4. 개발용 이메일과 비밀번호를 입력하여 실행합니다.
5. 응답의 `data.access_token` 값을 복사합니다.
6. Swagger 상단의 **Authorize**를 누릅니다.
7. 따옴표 없이 토큰만 붙여 넣습니다. Swagger가 `Bearer`를 자동으로 추가합니다.
8. Account 영역의 보호 API를 실행합니다.
9. Operator 영역은 운영자 계정으로 다시 로그인하고 토큰을 교체한 후 테스트합니다.

## 11. 전체 API 목록

| 방식 | 경로 | 접근 권한 | 기능 |
| --- | --- | --- | --- |
| GET | `/` | 공개 | 서비스 정보 |
| GET | `/health` | 공개 | 상태 확인 |
| GET | `/openapi.json` | 공개 | OpenAPI 명세 |
| GET | `/docs/` | 공개 | Swagger UI |
| POST | `/api/v1/auth/login` | 공개 | JWT 발급 |
| GET | `/api/v1/catalog/categories` | 공개 | 카테고리 목록 |
| GET | `/api/v1/content` | 공개 | 공개 콘텐츠 검색/필터 |
| GET | `/api/v1/content/<id>` | 공개 | 콘텐츠 상세 |
| GET | `/api/v1/live` | 공개 | 라이브 및 예정 방송 |
| GET | `/api/v1/me` | JWT | 현재 사용자 정보 |
| GET | `/api/v1/wallet` | JWT | 지갑 잔액 |
| GET | `/api/v1/wallet/packages` | 공개 | 포인트 상품 목록 |
| POST | `/api/v1/wallet/topups` | JWT | 고유 결제 참조값으로 포인트 적립 |
| POST | `/api/v1/content/<id>/unlock` | JWT | 광고/포인트/현금 잠금 해제 |
| GET | `/api/v1/operator/devices` | 운영자/관리자 | 헤드셋 목록 |
| POST | `/api/v1/operator/devices/actions` | 운영자/관리자 | 디바이스 일괄 명령 |
| POST | `/api/v1/operator/sync` | 운영자/관리자 | 재생 동기화 기록 생성 |

## 12. API 요청 예제

### 로그인

```bash
curl -X POST http://localhost:5000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"member@hominsu.local","password":"member1234"}'
```

응답 토큰을 저장합니다.

```bash
TOKEN='발급된-토큰'
```

PowerShell에서는 다음과 같이 저장합니다.

```powershell
$token = "발급된-토큰"
```

### 콘텐츠 필터

```bash
curl 'http://localhost:5000/api/v1/content?category=culture&feed=featured&q=경복궁'
```

`feed`는 `latest`, `featured`, `free` 중 하나입니다.

### 사용자와 지갑

```bash
curl http://localhost:5000/api/v1/me -H "Authorization: Bearer $TOKEN"
curl http://localhost:5000/api/v1/wallet -H "Authorization: Bearer $TOKEN"
```

### 콘텐츠 잠금 해제

```bash
curl -X POST http://localhost:5000/api/v1/content/1/unlock \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"method":"points"}'
```

`method`는 `ad`, `points`, `cash`를 지원합니다. 사용자와 콘텐츠 조합별로 한
번만 과금되며, 반복 요청은 기존 잠금 해제 정보를 반환합니다.

### 포인트 충전

```bash
curl -X POST http://localhost:5000/api/v1/wallet/topups \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"package_id":1,"reference":"manual-test-001"}'
```

성공한 충전마다 새로운 `reference`가 필요합니다. 현재 API는 결제가 완료된
것으로 가정하므로 운영 환경에서는 결제사 웹훅 검증을 추가해야 합니다.

### 디바이스 일괄 명령

운영자 토큰을 사용합니다.

```bash
curl -X POST http://localhost:5000/api/v1/operator/devices/actions \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"device_ids":[1,2],"action":"reboot","payload":{}}'
```

지원 명령은 `launch_content`, `stop_content`, `wake`, `sleep`, `reboot`,
`update`, `refresh_catalog`입니다.

### 헤드셋 동기화

```bash
curl -X POST http://localhost:5000/api/v1/operator/sync \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"device_ids":[1,2],"payload":{"content_id":1,"position_seconds":0}}'
```

현재 API는 명령과 동기화 기록을 DB에 저장합니다. 실제 헤드셋 전송을 위한
MQTT, WebSocket 또는 디바이스 에이전트는 별도 구현이 필요합니다.

## 13. 응답 형식과 상태 코드

성공 응답:

```json
{"data": {}}
```

오류 응답:

```json
{"error":{"code":"validation_error","message":"오류 설명"}}
```

| 상태 | 의미 |
| --- | --- |
| `200` | 조회 성공 또는 기존 결과 반환 |
| `201` | 리소스/거래 생성 성공 |
| `400` | 요청 데이터 오류 |
| `401` | JWT 없음, 오류 또는 만료 |
| `403` | 운영자 권한 없음 |
| `404` | 경로나 리소스 없음 |
| `409` | 잔액 부족 또는 중복 결제 참조값 |
| `422` | JWT 형식 오류 |

## 14. 개발 및 유지보수 명령

```bash
pytest
flask db current
flask db upgrade
flask seed
```

모델 변경 시 새 마이그레이션을 만들고 내용을 검토합니다.

```bash
flask db migrate -m "스키마 변경 설명"
flask db upgrade
```

이미 배포된 마이그레이션 파일을 새 변경사항 용도로 수정하면 안 됩니다.

## 15. 문제 해결

| 문제 | 해결 방법 |
| --- | --- |
| 루트에서 `not_found` | 최신 코드를 적용합니다. 현재 `/` 경로가 등록되어 있습니다. |
| Swagger가 열리지 않음 | 의존성을 설치하고 Uvicorn을 재시작한 뒤 `/docs/`를 엽니다. |
| `psql` 연결 실패 | PostgreSQL 서비스, 포트, 사용자, 비밀번호, URL을 확인합니다. |
| 테이블이 없다는 오류 | `flask db upgrade`를 실행합니다. |
| 개발 계정/데이터가 없음 | 마이그레이션 후 `flask seed`를 실행합니다. |
| Swagger `401` | 다시 로그인하고 새 토큰으로 **Authorize**를 실행합니다. |
| 디바이스 API `403` | 운영자 또는 관리자 토큰을 사용합니다. |
| JSON `404` | 서버에는 연결되었지만 API 경로가 잘못된 상태입니다. |
| 브라우저 CORS 오류 | 정확한 프런트엔드 주소를 `CORS_ORIGINS`에 추가합니다. |
| 포인트 충전 중복 오류 | 새로운 고유 `reference`를 사용합니다. |
| 5000 포트 사용 중 | 다른 프로세스를 종료하거나 포트를 변경하고 프런트엔드도 수정합니다. |

Ubuntu PostgreSQL 확인:

```bash
sudo systemctl status postgresql --no-pager
sudo journalctl -u postgresql --since "10 minutes ago"
```

Windows PostgreSQL 확인:

```powershell
Get-Service postgresql*
Get-Service postgresql* | Start-Service
```

## 16. 운영 배포 점검표

- DB, JWT, 시드 계정 및 비밀번호를 모두 교체합니다.
- 디버그 및 자동 재시작 모드를 끕니다.
- 관리형 PostgreSQL 백업과 최소 권한 계정을 사용합니다.
- 마이그레이션을 통제된 배포 단계에서 한 번만 실행합니다.
- HTTPS 프록시 또는 로드 밸런서 뒤에서 Uvicorn을 실행합니다.
- CORS를 실제 배포된 프런트엔드 주소로 제한합니다.
- 충전과 현금 구매 전에 결제사 검증을 추가합니다.
- 토큰 폐기/갱신, 속도 제한, 감사 로그, 모니터링 및 비밀 관리 정책을 추가합니다.
- 운영자 명령을 인증된 디바이스 전송 계층과 연결합니다.
