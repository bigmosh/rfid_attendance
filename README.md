# RFID attendance

Savonia UAS Bachelor of Engineering IoT thesis project:
**Securing IoT-Based Automated Attendance through Encrypted RFID Data
Transmission**.

The repository currently contains two independent parts:

- The proven Raspberry Pi edge application at the repository root. Its RC522
  and OLED hardware modules remain local-only and are not containerized.
- A FastAPI/PostgreSQL backend preparation layer in `backend/`, intended for
  deployment from Git through Coolify.

## Raspberry Pi edge application

The validated edge application still runs from the repository root:

```bash
source venv/bin/activate
python3 main.py
```

Do not install backend dependencies into the Raspberry Pi hardware virtual
environment. The edge application is not yet connected to the backend.

## Backend local setup

Prerequisites: Python 3.12+ and an available PostgreSQL database.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
cp .env.example .env
```

Set `DATABASE_URL` in `backend/.env` to a local PostgreSQL URL. Do not commit
this file.

Apply the initial schema, then seed the demo data:

```bash
alembic upgrade head
python3 -m scripts.seed_demo_data
```

Run the backend locally:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Verify the health check:

```bash
curl http://127.0.0.1:8000/health
```

## Migrations

Alembic reads `DATABASE_URL` through `app.config`. The committed
`0001_initial_schema` migration creates the initial PostgreSQL schema.

For later model changes, generate a migration from `backend/`, review it, and
apply it explicitly:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

Migrations are deliberately not run automatically when the container starts.
For Coolify, run `alembic upgrade head` as a controlled deployment operation
using the same image and `DATABASE_URL` environment variable.

## Tests

Edge tests:

```bash
python3 -m unittest discover -s tests -v
```

Backend tests:

```bash
cd backend
source .venv/bin/activate
pytest
```

The backend tests currently cover the health endpoint and request-schema
validation only. They do not require PostgreSQL or Raspberry Pi hardware.

## Docker and Coolify

Build from the repository root so the Dockerfile can copy `backend/`:

```bash
docker build -f backend/Dockerfile -t rfid-attendance-backend .
```

Run locally with a PostgreSQL URL supplied at runtime:

```bash
docker run --rm -p 8000:8000 \
  -e APP_ENV=development \
  -e LOG_LEVEL=INFO \
  -e DATABASE_URL='postgresql+psycopg://user:password@host:5432/attendance' \
  rfid-attendance-backend
```

For Coolify:

- Repository: this repository.
- Build pack/type: Dockerfile.
- Dockerfile location: `backend/Dockerfile`.
- Build context: repository root.
- Application port: `8000`.
- Environment: `DATABASE_URL`, `APP_ENV=production`, and `LOG_LEVEL=INFO`.
- Domain and HTTPS/TLS: configured and terminated by Coolify's reverse proxy.

No database credentials, domains, or application secrets belong in the Git
repository or Dockerfile.

## Current backend scope

`GET /health` is available. The attendance endpoint contract, SQLAlchemy
models, Alembic schema, and seed script are prepared, but
`POST /api/v1/attendance` is intentionally not implemented yet. The Raspberry
Pi continues to use its local temporary lookup until that endpoint is approved
and deployed.
