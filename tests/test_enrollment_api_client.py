"""Mocked enrollment HTTP client tests; no Pi hardware or network is used."""

from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import Mock, patch

import requests

from services import enrollment


EXPIRES_AT = "2026-09-05T12:00:00+00:00"


def _response(status_code=200, body=None, json_error=False):
    response = Mock(status_code=status_code)
    if json_error:
        response.json.side_effect = ValueError("invalid JSON")
    else:
        response.json.return_value = body
    return response


class EnrollmentApiClientTests(TestCase):
    def setUp(self):
        self.api_base_url_patcher = patch.object(
            enrollment,
            "API_BASE_URL",
            "https://attendance.example.test",
        )
        self.device_id_patcher = patch.object(enrollment, "DEVICE_ID", "attendance-pi-01")
        self.timeout_patcher = patch.object(enrollment, "REQUEST_TIMEOUT_SECONDS", 5.0)
        self.api_base_url_patcher.start()
        self.device_id_patcher.start()
        self.timeout_patcher.start()
        self.addCleanup(self.api_base_url_patcher.stop)
        self.addCleanup(self.device_id_patcher.stop)
        self.addCleanup(self.timeout_patcher.stop)

    @patch("services.enrollment.requests.get")
    def test_no_enrollment_returns_none_and_uses_device_poll_endpoint(self, get):
        get.return_value = _response(body={"status": "none"})

        result = enrollment.poll_enrollment()

        self.assertEqual(result.status, "none")
        self.assertIsNone(result.enrollment)
        get.assert_called_once_with(
            "https://attendance.example.test/api/v1/devices/attendance-pi-01/enrollment",
            timeout=5.0,
        )

    @patch("services.enrollment.requests.get")
    def test_pending_enrollment_is_parsed_for_mode_transition(self, get):
        get.return_value = _response(
            body={
                "status": "pending",
                "enrollment_id": 12,
                "student": {"id": 3, "student_number": "ST003", "name": "John Doe"},
                "expires_at": EXPIRES_AT,
            }
        )

        result = enrollment.poll_enrollment()

        self.assertEqual(result.status, "pending")
        self.assertEqual(result.enrollment.id, 12)
        self.assertEqual(result.enrollment.student_name, "John Doe")
        self.assertEqual(result.enrollment.expires_at, datetime(2026, 9, 5, 12, tzinfo=timezone.utc))

    @patch("services.enrollment.requests.get", side_effect=requests.Timeout)
    def test_poll_timeout_returns_network_error_without_crashing(self, _get):
        result = enrollment.poll_enrollment()
        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "network_error")

    @patch("services.enrollment.requests.get", side_effect=requests.ConnectionError)
    def test_poll_connection_failure_returns_network_error(self, _get):
        result = enrollment.poll_enrollment()
        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "network_error")

    @patch("services.enrollment.requests.get")
    def test_poll_malformed_response_returns_server_error(self, get):
        get.return_value = _response(json_error=True)
        result = enrollment.poll_enrollment()
        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason, "server_error")

    @patch("services.enrollment.requests.post")
    def test_successful_card_submission_returns_completed_result(self, post):
        post.return_value = _response(
            body={
                "success": True,
                "status": "completed",
                "student": {"id": 3, "student_number": "ST003", "name": "John Doe"},
                "card_status": "active",
            }
        )

        result = enrollment.submit_enrollment_card(12, "1-2-3-4")

        self.assertTrue(result.success)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.student_name, "John Doe")
        post.assert_called_once_with(
            "https://attendance.example.test/api/v1/enrollments/12/card",
            json={"device_id": "attendance-pi-01", "card_uid": "1-2-3-4"},
            timeout=5.0,
        )

    @patch("services.enrollment.requests.post")
    def test_duplicate_card_keeps_pending_enrollment_state(self, post):
        post.return_value = _response(
            body={"success": False, "status": "pending", "reason": "card_already_assigned"}
        )
        result = enrollment.submit_enrollment_card(12, "1-2-3-4")
        self.assertFalse(result.success)
        self.assertEqual(result.status, "pending")
        self.assertEqual(result.reason, "card_already_assigned")

    @patch("services.enrollment.requests.post")
    def test_cancelled_and_expired_results_are_preserved(self, post):
        post.return_value = _response(
            body={"success": False, "status": "cancelled", "reason": "enrollment_cancelled"}
        )
        self.assertEqual(enrollment.submit_enrollment_card(12, "1-2-3-4").reason, "enrollment_cancelled")
        post.return_value = _response(
            body={"success": False, "status": "expired", "reason": "enrollment_expired"}
        )
        self.assertEqual(enrollment.submit_enrollment_card(12, "1-2-3-4").reason, "enrollment_expired")

    @patch("services.enrollment.requests.post", side_effect=requests.ConnectionError)
    def test_card_submission_network_failure_does_not_produce_attendance_result(self, _post):
        result = enrollment.submit_enrollment_card(12, "1-2-3-4")
        self.assertFalse(result.success)
        self.assertEqual(result.status, "pending")
        self.assertEqual(result.reason, "network_error")
