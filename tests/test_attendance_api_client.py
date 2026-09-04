"""Mocked HTTPS client tests; no Raspberry Pi hardware or network is used."""

from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import Mock, patch

import requests

from services import attendance


EVENT_TIME = datetime(2026, 9, 4, 10, 30, tzinfo=timezone(timedelta(hours=3)))


def _response(status_code=200, body=None, json_error=False):
    response = Mock(status_code=status_code)
    if json_error:
        response.json.side_effect = ValueError("invalid JSON")
    else:
        response.json.return_value = body
    return response


class AttendanceApiClientTests(TestCase):
    def setUp(self):
        self.api_base_url_patcher = patch.object(
            attendance,
            "API_BASE_URL",
            "https://attendance.example.test",
        )
        self.device_id_patcher = patch.object(attendance, "DEVICE_ID", "attendance-pi-01")
        self.timeout_patcher = patch.object(attendance, "REQUEST_TIMEOUT_SECONDS", 5.0)
        self.api_base_url_patcher.start()
        self.device_id_patcher.start()
        self.timeout_patcher.start()
        self.addCleanup(self.api_base_url_patcher.stop)
        self.addCleanup(self.device_id_patcher.stop)
        self.addCleanup(self.timeout_patcher.stop)

    @patch("services.attendance.requests.post")
    def test_success_returns_student_result_and_sends_correct_payload(self, post):
        post.return_value = _response(
            body={
                "success": True,
                "student": {"id": 1, "student_number": "ST001", "name": "Student 1"},
                "attendance": {"id": 42, "status": "recorded"},
            }
        )

        result = attendance.submit_attendance("77-48-28-61-92", EVENT_TIME)

        self.assertTrue(result.success)
        self.assertEqual(result.student_name, "Student 1")
        self.assertEqual(result.student_number, "ST001")
        self.assertEqual(result.attendance_id, 42)
        post.assert_called_once_with(
            "https://attendance.example.test/api/v1/attendance",
            json={
                "device_id": "attendance-pi-01",
                "card_uid": "77-48-28-61-92",
                "event_time": "2026-09-04T10:30:00+03:00",
            },
            timeout=5.0,
        )

    @patch("services.attendance.requests.post")
    def test_unknown_card_returns_expected_reason(self, post):
        post.return_value = _response(body={"success": False, "reason": "unknown_card"})

        result = attendance.submit_attendance("1-2-3-4-5", EVENT_TIME)

        self.assertFalse(result.success)
        self.assertEqual(result.reason, "unknown_card")

    @patch("services.attendance.requests.post")
    def test_disabled_card_returns_expected_reason(self, post):
        post.return_value = _response(body={"success": False, "reason": "card_disabled"})

        result = attendance.submit_attendance("77-48-28-61-92", EVENT_TIME)

        self.assertFalse(result.success)
        self.assertEqual(result.reason, "card_disabled")

    @patch("services.attendance.requests.post")
    def test_unknown_device_returns_expected_reason(self, post):
        post.return_value = _response(body={"success": False, "reason": "unknown_device"})

        result = attendance.submit_attendance("77-48-28-61-92", EVENT_TIME)

        self.assertFalse(result.success)
        self.assertEqual(result.reason, "unknown_device")

    @patch("services.attendance.requests.post", side_effect=requests.Timeout)
    def test_timeout_returns_network_error(self, _post):
        result = attendance.submit_attendance("77-48-28-61-92", EVENT_TIME)

        self.assertFalse(result.success)
        self.assertEqual(result.reason, "network_error")

    @patch("services.attendance.requests.post", side_effect=requests.ConnectionError)
    def test_connection_failure_returns_network_error(self, _post):
        result = attendance.submit_attendance("77-48-28-61-92", EVENT_TIME)

        self.assertFalse(result.success)
        self.assertEqual(result.reason, "network_error")

    @patch("services.attendance.requests.post")
    def test_http_500_returns_server_error(self, post):
        post.return_value = _response(status_code=500)

        result = attendance.submit_attendance("77-48-28-61-92", EVENT_TIME)

        self.assertFalse(result.success)
        self.assertEqual(result.reason, "server_error")

    @patch("services.attendance.requests.post")
    def test_malformed_json_returns_server_error(self, post):
        post.return_value = _response(json_error=True)

        result = attendance.submit_attendance("77-48-28-61-92", EVENT_TIME)

        self.assertFalse(result.success)
        self.assertEqual(result.reason, "server_error")

    @patch("services.attendance.requests.post")
    def test_unexpected_response_body_returns_server_error(self, post):
        post.return_value = _response(body={"success": True, "student": {}})

        result = attendance.submit_attendance("77-48-28-61-92", EVENT_TIME)

        self.assertFalse(result.success)
        self.assertEqual(result.reason, "server_error")
