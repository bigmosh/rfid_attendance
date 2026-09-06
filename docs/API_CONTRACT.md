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

## Student administration

All student list endpoints use `page` starting at 1 and accept `page_size`
from 1 to 100. Administrative requests return safe `404` and `409` responses
for expected missing-resource and conflict cases; they never expose database
details.

### List students

`GET /api/v1/students?page=1&page_size=20&search=ST001&status=active`

`search` matches student name and student number. `status` is optional and is
either `active` or `inactive`.

```json
{
  "items": [
    {
      "id": 1,
      "student_number": "ST001",
      "name": "Student 1",
      "status": "active",
      "rfid_card_status": "active"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1,
  "pages": 1
}
```

### Create, view, and update a student

`POST /api/v1/students`

```json
{
  "student_number": "ST003",
  "name": "John Doe"
}
```

Student numbers are trimmed and normalised to uppercase; names have redundant
whitespace collapsed. A duplicate student number returns HTTP `409`:

```json
{
  "detail": {
    "code": "student_number_exists",
    "message": "Student number already exists"
  }
}
```

`GET /api/v1/students/{student_id}` returns student information and the active
card, or the most recently disabled card if there is no active card.

`PATCH /api/v1/students/{student_id}` accepts one or more of `name`,
`student_number`, and `status` (`active` or `inactive`). Students are not
hard-deleted. Setting `status` to `inactive` preserves historical attendance
but rejects future attendance events.

`GET /api/v1/students/{student_id}/attendance?page=1&page_size=10` returns the
same newest-first attendance item format as the general attendance list, scoped
to one student.

### Manual RFID card administration

`POST /api/v1/students/{student_id}/rfid-card` manually assigns a first card:

```json
{
  "uid": "77-48-28-61-92"
}
```

UIDs are trimmed and normalised to hyphen-separated decimal values. A UID must
be unique; assigning a second active card returns HTTP `409` with code
`active_card_exists`.

`PATCH /api/v1/students/{student_id}/rfid-card` changes the current card's
status:

```json
{
  "status": "disabled"
}
```

`POST /api/v1/students/{student_id}/rfid-card/replace` accepts the same UID
body as assignment. It disables the currently active card and inserts a new
active card in one transaction. Historical attendance continues to reference
the old card.

`POST /api/v1/students/{student_id}/rfid-card/unassign` safely removes the
card from attendance eligibility by disabling it. It intentionally does not
hard-delete the card row or rewrite historical attendance.

These endpoints remain available for manual administrative or development
assignment. Device-assisted enrollment is documented below.

## Physical RFID enrollment

Stage 3 uses normal HTTPS polling. The backend never connects directly to a
Raspberry Pi. The dashboard creates one pending request for a selected active
device; the Pi polls every few seconds and enters enrollment mode only while
that request remains pending.

### Create enrollment

`POST /api/v1/enrollments`

```json
{
  "student_id": 3,
  "device_id": "attendance-pi-01"
}
```

The student and device must both be active. At most one request can be pending
per device. The backend calculates `expires_at` in UTC from
`RFID_ENROLLMENT_TIMEOUT_SECONDS` (default 60 seconds).

### Poll from the Pi

`GET /api/v1/devices/{device_id}/enrollment`

No active request:

```json
{ "status": "none" }
```

Pending request:

```json
{
  "status": "pending",
  "enrollment_id": 15,
  "student": {
    "id": 3,
    "student_number": "ST003",
    "name": "John Doe"
  },
  "expires_at": "2026-09-05T10:30:00Z"
}
```

### Submit the tapped card

`POST /api/v1/enrollments/{enrollment_id}/card`

```json
{
  "device_id": "attendance-pi-01",
  "card_uid": "123-45-67-89"
}
```

On success the request is marked `completed`; if the student already has an
active card, it is disabled and the new card becomes active. Historical
attendance remains linked to the old card.

```json
{
  "success": true,
  "status": "completed",
  "student": { "id": 3, "student_number": "ST003", "name": "John Doe" },
  "card_status": "active"
}
```

If a UID is already assigned, the request stays pending so the administrator
can tap another card:

```json
{
  "success": false,
  "status": "pending",
  "reason": "card_already_assigned"
}
```

`POST /api/v1/enrollments/{enrollment_id}/cancel` safely changes a pending
request to `cancelled`. `GET /api/v1/enrollments/{enrollment_id}` supports the
dashboard modal's short-lived progress polling. Pending requests become
`expired` lazily when polled, viewed, or submitted after `expires_at`.

`GET /api/v1/devices` is a read-only device list used for enrollment selection.
Manual student-card assignment remains available for administrative and
development use.

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
      "attendance_date": "2026-09-05",
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

This endpoint resolves the device, RFID card, and student from PostgreSQL. It
persists at most one attendance record per student for each `APP_TIMEZONE`
calendar day.

Request:

```json
{
  "device_id": "attendance-pi-01",
  "card_uid": "77-48-28-61-92",
  "event_time": "2026-09-03T21:43:36+03:00"
}
```

`event_time` must be an ISO 8601 datetime with a timezone offset. It records
when the Raspberry Pi observed the card. The backend stores its own UTC-aware
`server_received_at` timestamp when accepting the request, then derives
`attendance_date` by converting that receipt timestamp to `APP_TIMEZONE`.
`attendance_date` is the authoritative date for the one-per-day rule; the Pi
timestamp is retained and is not repurposed.

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
    "attendance_date": "2026-09-03",
    "event_time": "2026-09-03T21:43:36+03:00",
    "server_received_at": "2026-09-03T18:43:36Z"
  }
}
```

### Repeat scan on the same local day

A repeat scan by the same valid student on the same `attendance_date` is a
successful outcome. It does not create a row; the backend returns the original
attendance record for that day:

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
    "status": "already_recorded_today",
    "attendance_date": "2026-09-03",
    "event_time": "2026-09-03T21:43:36+03:00",
    "server_received_at": "2026-09-03T18:43:36Z"
  }
}
```

The database enforces this rule with `UNIQUE(student_id, attendance_date)`.
The service checks first for a clear response, then catches a uniqueness race,
fetches the canonical row, and returns `already_recorded_today` instead of a
database error.

## Encrypted attendance transport

`POST /api/v1/attendance/encrypted` is the Raspberry Pi production transport
for Stage 4. HTTPS remains mandatory. AES-128-GCM adds application-level
confidentiality and authenticated tamper detection for the RFID UID and Pi
event timestamp before they enter the existing HTTPS request path.

The Pi serializes this plaintext deterministically using UTF-8 JSON with sorted
keys and compact separators:

```json
{
  "card_uid": "77-48-28-61-92",
  "event_time": "2026-09-06T14:20:10+03:00"
}
```

It generates a cryptographically random, unique 12-byte nonce for every
message. AES-GCM produces ciphertext with its authentication tag appended.
The `device_id` is deliberately outside the ciphertext so the backend can find
the device key, but is also supplied as UTF-8 AES-GCM Associated Authenticated
Data (AAD). Changing the device identity invalidates authentication.

Request transport:

```json
{
  "device_id": "attendance-pi-01",
  "nonce": "<base64-encoded-12-byte-nonce>",
  "ciphertext": "<base64-encoded-ciphertext-and-tag>"
}
```

The backend validates the outer request, resolves the active device, loads its
environment-configured Base64 AES-128 key, authenticates/decrypts with AAD,
validates the decrypted JSON as the normal attendance payload, then calls the
same attendance service used by the plaintext endpoint. Successful responses,
including `recorded` and `already_recorded_today`, have exactly the normal
attendance response semantics.

Expected encrypted transport failures return a safe `success: false` response:

```json
{ "success": false, "reason": "authentication_failed" }
```

Other safe reasons are `unknown_device`, `device_key_not_configured`,
`invalid_encrypted_payload`, and `invalid_plaintext_payload`. They reveal no
key, nonce, plaintext, or database details. Tampered ciphertext, a wrong key,
or a modified AAD/device ID all produce `authentication_failed` and create no
attendance row.

The existing `POST /api/v1/attendance` plaintext endpoint remains temporarily
available for baseline comparison and development regression testing. The Pi
does not fall back to it after encrypted transmission has been configured.
Plaintext attendance may be removed or disabled in a later hardening stage.

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

Inactive student:

```json
{
  "success": false,
  "reason": "student_inactive"
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
`last_seen` timestamp. A migration backfills `attendance_date` from existing
`server_received_at` values in `APP_TIMEZONE`; for historical duplicate rows it
retains the earliest `server_received_at` (then lowest id) per student/day and
removes later duplicate test scans before applying the unique constraint.
