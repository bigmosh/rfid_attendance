# RFID attendance

Savonia UAS Bachelor of Engineering IoT thesis project:
**Securing IoT-Based Automated Attendance through Encrypted RFID Data
Transmission**.

The repository currently contains two independent parts:

- The proven Raspberry Pi edge application at the repository root. Its RC522
  and OLED hardware modules remain local-only and are not containerized.
- A FastAPI/PostgreSQL backend preparation layer in `backend/`, intended for
  deployment from Git through Coolify.
- A React dashboard in `frontend/` that reads dashboard data through FastAPI.

The complete data path is Raspberry Pi → HTTPS → FastAPI → PostgreSQL →
dashboard. The dashboard provides attendance visibility and Stage 2 student/
RFID-card administration.

## Raspberry Pi edge application

The validated edge application still runs from the repository root:

```bash
source venv/bin/activate
python3 main.py
```

Do not install backend dependencies into the Raspberry Pi hardware virtual
environment.

### Edge API configuration

The edge application sends RFID events to the backend over HTTPS. Configure
these environment variables in the shell that starts `main.py`; do not place a
real production URL in source code:

```bash
export API_BASE_URL='https://<your-configured-domain>'
export DEVICE_ID='attendance-pi-01'
export REQUEST_TIMEOUT_SECONDS='5'
```

If `API_BASE_URL` is not configured, the application uses the safe placeholder
`https://attendance.example.invalid` and shows a network error rather than
sending attendance data over plain HTTP.

The Pi creates the event timestamp with `datetime.now().astimezone()`, using
its configured system timezone. It does not fabricate a timezone offset.

### Physical RFID enrollment polling

The Pi remains in normal attendance mode unless the dashboard creates a
pending enrollment for its configured `DEVICE_ID`. It checks the backend using
scheduled HTTPS polling without sleeping the RFID loop. Configure the polling
interval in the Pi environment file:

```text
ENROLLMENT_POLL_SECONDS=3
```

When the backend reports a pending request, the Pi enters enrollment mode and
the next card UID is sent only to the enrollment endpoint, never to attendance.
On completion, cancellation, expiration, or terminal failure it returns to
normal attendance. A duplicate-card or network submission error keeps the
enrollment active after the card is removed, allowing a safe retry.

### Deploying edge updates to the Raspberry Pi

Option A — use Git only if the Pi directory is already a clone configured with
this repository's `origin` remote:

```bash
cd /home/raspberry-user/rfid-attendance
git pull --ff-only origin main
source venv/bin/activate
python3 -m pip install -r requirements.txt
export API_BASE_URL='https://<your-configured-domain>'
export DEVICE_ID='attendance-pi-01'
export REQUEST_TIMEOUT_SECONDS='5'
python3 -m unittest discover -s tests -v
python3 main.py
```

Option B — copy the project from the development laptop without replacing the
Pi virtual environment:

```bash
rsync -avh \
  --exclude='venv/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  /Users/faskt/Documents/projects/rfid_project/ \
  raspberry-user@attendance-pi.local:/home/raspberry-user/rfid-attendance/
```

Then run the same activation, dependency-installation, configuration, test,
and `python3 main.py` commands shown in Option A.

### Appliance startup with systemd

Once the end-to-end application has been manually verified on the Pi, install
the systemd unit. The unit starts after the network-online target, restarts the
application three seconds after a crash, and sends normal application output to
the system journal. A temporary backend outage does not stop the edge process:
the existing attendance client displays a network error and continues polling.
When systemd stops or restarts the unit, the application handles SIGTERM using
its normal cleanup path for the RFID reader and OLED.

Copy the service file:

```bash
cd /home/raspberry-user/rfid-attendance
sudo cp deploy/attendance.service /etc/systemd/system/attendance.service
```

Create the production environment file from the committed placeholder example:

```bash
sudo cp deploy/rfid-attendance.env.example /etc/rfid-attendance.env
sudo nano /etc/rfid-attendance.env
```

Set its values to the real HTTPS API domain and device configuration. Do not
place API keys or future AES keys in the repository:

```text
API_BASE_URL=https://<your-configured-domain>
DEVICE_ID=attendance-pi-01
REQUEST_TIMEOUT_SECONDS=5
```

Restrict the environment-file permissions, load the new unit, enable it at
boot, and start it now:

```bash
sudo chmod 600 /etc/rfid-attendance.env
sudo systemctl daemon-reload
sudo systemctl enable attendance.service
sudo systemctl start attendance.service
```

Check the running service and follow its logs:

```bash
sudo systemctl status attendance.service
journalctl -u attendance.service -f
```

Manage it when needed:

```bash
sudo systemctl restart attendance.service
sudo systemctl stop attendance.service
```

Perform the final appliance test with:

```bash
sudo reboot
```

After reboot, do not manually run `python3 main.py`; systemd owns the process.

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

Apply the schema. The seed command is an optional local demo utility only:

```bash
alembic upgrade head
# Optional: creates the two documented demo students/cards and demo device.
# Do not run this after the one-time 0006_purge_students reset migration.
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

The database health check performs only `SELECT 1` and returns no connection
details. It requires a reachable local database:

```bash
curl http://127.0.0.1:8000/health/db
```

### Dashboard API configuration

The read-only dashboard APIs use `APP_TIMEZONE` for the `attendance_today`
summary and date filtering. For the Finland demonstration, configure:

```text
APP_TIMEZONE=Europe/Helsinki
```

When the frontend is deployed on a separate domain, configure a strict,
comma-separated CORS allowlist on the backend. Do not use `*` in production:

```text
CORS_ORIGINS=https://<your-dashboard-domain>
```

Multiple trusted origins can be supplied as a comma-separated value, for
example a production dashboard and a local Vite development server.

## Dashboard frontend

The React dashboard has Overview, Attendance, Students, Student Details, and
a Devices placeholder route. Overview and Attendance poll the backend every
eight seconds so a newly scanned card appears without a manual browser refresh.

### Student and RFID-card lifecycle

Students are never hard-deleted through the dashboard. An administrator can
set a student to `inactive`, preserving the student's RFID-card records and
all historical attendance. An inactive student's future RFID scans return the
normal application response `{"success": false, "reason": "student_inactive"}`
and do not create attendance rows. Reactivating the student restores normal
attendance eligibility when their card is also active.

The dashboard supports physical device-assisted enrollment and retains manual
UID assignment as a secondary administrative/development option. A student may
have one active RFID card. Replacing a card disables the old card and creates a
new active row, retaining every historical attendance reference. “Unassign” is
deliberately implemented as disabling the active card, not deleting a row, so
attendance history remains intact.

Run it locally:

```bash
cd frontend
cp .env.example .env
# Set VITE_API_BASE_URL to the local or deployed FastAPI base URL.
npm install
npm run dev
```

`VITE_API_BASE_URL` is a public, build-time browser value. It must contain only
the FastAPI base URL, never database credentials, keys, or secrets.

Validate TypeScript and produce a production build:

```bash
npm run typecheck
npm run build
```

### Frontend Coolify deployment

Deploy `frontend/` as a separate Coolify application:

- Build type: Dockerfile
- Base directory: `/frontend`
- Dockerfile location: `Dockerfile`
- Exposed application port: `80`
- Build environment variable: `VITE_API_BASE_URL=https://<your-api-domain>`

The Docker image builds Vite with Node and serves the resulting static files
with nginx. Its nginx configuration falls back to `index.html`, so direct
browser refreshes of `/attendance` work correctly.

Before deploying the frontend, add its final HTTPS domain to the backend
application's `CORS_ORIGINS` value and redeploy the backend. Also set
`APP_TIMEZONE=Europe/Helsinki` in the backend environment for the demonstration.

## Migrations

Alembic reads `DATABASE_URL` through `app.config`. The committed
`0001_initial_schema` migration creates the initial PostgreSQL schema.
`0003_student_status` adds the non-destructive student lifecycle status and a
PostgreSQL partial unique index that allows at most one active RFID card per
student.
`0004_rfid_enrollment` adds device-scoped enrollment history, expiration, and
the one-pending-enrollment-per-device constraint.

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

The backend tests cover health endpoints, dashboard APIs, attendance outcomes,
daily attendance uniqueness and migration backfill, student/card lifecycle
operations, request-schema validation, model constraints, and idempotent seed
data. They use mocks and in-memory SQLite only; they do not require PostgreSQL
or Raspberry Pi hardware.

## Docker and Coolify

Build from the backend directory, which matches Coolify's `/backend` base
directory:

```bash
cd backend
docker build -t rfid-attendance-backend .
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
- Base directory: `/backend`.
- Dockerfile location: `Dockerfile`.
- Application port: `8000`.
- Environment: `DATABASE_URL`, `APP_ENV=production`, and `LOG_LEVEL=INFO`.
- Additional dashboard environment: `APP_TIMEZONE=Europe/Helsinki` and a
  strict `CORS_ORIGINS` allowlist containing the frontend domain.
- Domain and HTTPS/TLS: configured and terminated by Coolify's reverse proxy.

No database credentials, domains, or application secrets belong in the Git
repository or Dockerfile.

### Post-deployment database operations

After the Coolify application is deployed with `DATABASE_URL` configured, open
its application terminal. The container work directory is `/app`. Apply the
migrations explicitly:

```bash
cd /app
python -m alembic upgrade head
```

The migration command is explicit and is not run automatically at startup.
`scripts.seed_demo_data` remains an idempotent, manually invoked local demo
utility; it is never invoked by application startup or deployment. Do not run
it after `0006_purge_students`, which intentionally leaves students, cards,
attendance, and enrollment requests empty while preserving registered devices.

Optionally confirm that the database is at the current Alembic revision:

```bash
python -m alembic current
```

Afterward, test this path through the public Coolify domain:

```text
https://<your-configured-domain>/health/db
```

### Stage 3 physical card enrollment deployment

The backend calculates enrollment expiry using a timezone-aware UTC timestamp.
Set this Coolify backend environment variable before deploying Stage 3:

```text
RFID_ENROLLMENT_TIMEOUT_SECONDS=60
```

After the new backend image is deployed, run the controlled migration in its
Coolify terminal:

```bash
cd /app
python -m alembic upgrade head
python -m alembic current
```

Then deploy the frontend. The student details page lets an administrator select
an active attendance device and opens an enrollment modal. It polls the
enrollment status every two seconds only while that modal is open.

Finally update the Pi from Git and add `ENROLLMENT_POLL_SECONDS=3` to
`/etc/rfid-attendance.env` before restarting the existing service:

```bash
cd /home/raspberry-user/rfid-attendance
git pull --ff-only origin main
sudo nano /etc/rfid-attendance.env
sudo systemctl restart attendance.service
```

Enrollment architecture:

```text
Dashboard → FastAPI/PostgreSQL ← Pi polls every 3 seconds
                                      ↓
                               OLED: Tap new card
                                      ↓
                                  RFID UID submit
                                      ↓
                           card assignment and normal mode
```

### Stage 3.1 daily attendance deployment

Daily attendance is one persisted row per student per `APP_TIMEZONE` local
calendar day. The backend keeps the Pi-provided `event_time`, generates the
authoritative UTC `server_received_at`, and derives `attendance_date` from the
receipt timestamp in `APP_TIMEZONE`.

The `0005_daily_attendance` migration backfills existing rows. If production
contains previous same-day test scans, it deterministically retains the
earliest `server_received_at` row (then the lowest id) for each student/date,
logs the number of later duplicate rows removed through PostgreSQL migration
output, and then creates `UNIQUE(student_id, attendance_date)`.

`APP_TIMEZONE=Europe/Helsinki` is already required backend configuration; this
stage introduces no additional environment variable. After deploying the new
backend image, run only the controlled migration in the Coolify terminal:

```bash
cd /app
python -m alembic upgrade head
python -m alembic current
```

The Pi receives `recorded` for a first scan and `already_recorded_today` for a
repeat scan. Both are successful. The latter displays `ALREADY RECORDED` and
returns to the normal ready screen; it does not create a dashboard row.

After the backend migration and frontend deployment, update the Pi application
and restart its existing systemd service. No Pi environment-variable change is
required for this stage:

```bash
cd /home/raspberry-user/rfid-attendance
git pull --ff-only origin main
sudo systemctl restart attendance.service
sudo systemctl status attendance.service
```

### Stage 4 AES-128-GCM encrypted attendance deployment

HTTPS remains enabled and terminates at Coolify as before. Stage 4 adds an
application-level AES-128-GCM layer for normal Pi attendance payloads:

```text
RFID UID + Pi event time
        ↓
deterministic JSON serialization
        ↓
AES-128-GCM (fresh random 12-byte nonce; device_id as AAD)
        ↓
device_id + nonce + ciphertext over HTTPS
        ↓
FastAPI device-key lookup and AES-GCM authentication/decryption
        ↓
existing attendance validation, daily deduplication, PostgreSQL
```

AES-GCM provides authenticated encryption: a tampered ciphertext, wrong key,
or modified `device_id`/AAD is rejected without creating attendance. It is an
additional protection layer, not a replacement for TLS. The design uses one
shared 16-byte AES-128 key per device, no key rotation or replay-nonce database
in this thesis stage.

Generate a key locally only when configuring the production environments; do
not commit or paste its output into documentation, source, or Git history:

```bash
python3 - <<'PY'
import base64
import os
print(base64.b64encode(os.urandom(16)).decode("ascii"))
PY
```

Configure the generated value in Coolify as one JSON environment variable:

```text
DEVICE_AES_KEYS_JSON={"attendance-pi-01":"<base64-encoded-16-byte-key>"}
```

Configure the identical value on the Pi in `/etc/rfid-attendance.env`:

```text
DEVICE_AES_KEY_BASE64=<base64-encoded-16-byte-key>
```

The Pi validates that this decodes to exactly 16 bytes at startup. A missing,
malformed, or wrong-length key stops the application clearly; encrypted mode
never silently downgrades to `POST /api/v1/attendance`. Encryption and backend
authentication timings are logged at debug level in milliseconds for later
thesis measurements, without logging plaintext, keys, or ciphertext.

Production sequence after reviewing this change:

1. Set `DEVICE_AES_KEYS_JSON` in the Coolify backend environment and deploy
   the backend image. No database migration is required; Alembic remains at
   `0005_daily_attendance`.
2. Update the Pi code and install the declared dependency in its existing venv.
3. Add `DEVICE_AES_KEY_BASE64` to `/etc/rfid-attendance.env` with permissions
   still restricted to root.
4. Restart `attendance.service` and verify its journal before testing a card.

Physical enrollment traffic remains its existing HTTPS JSON flow in this stage.
The plaintext attendance endpoint remains available only for baseline
comparison and regression testing; it is not used by the Stage 4 Pi client.

## Current backend scope

`GET /health`, `GET /health/db`, attendance endpoints, dashboard endpoints,
and student/card administration endpoints are available. The Raspberry Pi
continues to use `POST /api/v1/attendance`; its proven RFID/OLED modules are
not part of the backend or dashboard container deployments.
