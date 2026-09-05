# Attendance API contract

This document defines the first Raspberry Pi to backend contract. It is
intentionally normal JSON over HTTPS; application-layer AES encryption,
device authentication, and replay protection are later milestones.

The public domain is configured by Coolify and is not hardcoded by the
application. The route below is relative to that future domain.

## Health check

`GET /health`

Response:

```json
{
  "status": "ok"
}
```

The endpoint is implemented now. It is suitable for Coolify health checks and
does not expose configuration or database details.

## Dashboard read APIs

`GET /api/v1/dashboard/summary` returns real counts for students, attendance
in the configured application timezone, registered devices, and active RFID
cards:

```json
{
  "total_students": 2,
  "attendance_today": 8,
  "registered_devices": 1,
  "active_rfid_cards": 2
}
```

`GET /api/v1/attendance` returns newest-first attendance records. It accepts
optional `page`, `page_size`, `search`, `date` (`YYYY-MM-DD`), and `device_id`
query parameters. `page` starts at 1 and `page_size` is limited to 1–100.
Every item includes timezone-aware `event_time` and `server_received_at`
values:

```json
{
  "items": [
    {
      "id": 10,
      "student": {
        "id": 1,
        "student_number": "ST001",
        "name": "Student 1"
      },
      "device": {
        "device_id": "attendance-pi-01",
        "name": "Main Attendance Device"
      },
      "event_time": "2026-09-05T09:04:00+03:00",
      "server_received_at": "2026-09-05T06:04:01Z",
      "status": "recorded"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 42,
  "pages": 3
}
```

## Record attendance

`POST /api/v1/attendance`

This endpoint is implemented. It resolves the device, RFID card, and student
from PostgreSQL and creates one attendance record for each valid request.

Request:

```json
{
  "device_id": "attendance-pi-01",
  "card_uid": "77-48-28-61-92",
  "event_time": "2026-09-03T21:43:36+03:00"
}
```

`event_time` must be an ISO 8601 datetime with a timezone offset. It records
when the Raspberry Pi observed the card. The backend will additionally store
its own UTC-aware `server_received_at` timestamp when accepting the request.

### Successful response

```json
{
  "success": true,
  "student": {
    "id": 1,
    "student_number": "ST001",
    "name": "Student 1"
  },
  "attendance": {
    "id": 123,
    "status": "recorded",
    "event_time": "2026-09-03T21:43:36+03:00",
    "server_received_at": "2026-09-03T18:43:36Z"
  }
}
```

### Predictable failure responses

Unknown card:

```json
{
  "success": false,
  "reason": "unknown_card"
}
```

Disabled card:

```json
{
  "success": false,
  "reason": "card_disabled"
}
```

Unknown device:

```json
{
  "success": false,
  "reason": "unknown_device"
}
```

Expected domain outcomes return HTTP `200` with `success: false`, so the
Raspberry Pi can process them without interpreting them as backend failures.
An unknown or inactive device returns `unknown_device`; this first contract
does not distinguish a disabled device separately.

### Validation and server errors

`device_id`, `card_uid`, and `event_time` are required. `event_time` must be
an ISO 8601 datetime with a timezone offset. Missing fields or a timezone-naive
timestamp return FastAPI's HTTP `422` validation response.

Unexpected database failures are rolled back, logged by the backend, and
return HTTP `500` with a generic error message. No database details are sent
to the client.

For every request from a known active device, the backend updates that device's
`last_seen` timestamp. There is deliberately no server-side time-window
deduplication in this phase: each valid POST creates one attendance row.
