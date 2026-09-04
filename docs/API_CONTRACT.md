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

## Record attendance

`POST /api/v1/attendance`

This endpoint is documented and its request/response schemas are prepared,
but its route and database logic are intentionally deferred to the next
approved milestone.

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
