"""Coordinator tests with fake hardware module imports; no Pi packages are used."""

import importlib
import sys
import types
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from services.attendance import AttendanceResult
from services.enrollment import Enrollment, EnrollmentPollResult, EnrollmentSubmitResult


def _load_main_with_fake_hardware():
    sys.modules.pop("main", None)
    fake_display = types.ModuleType("hardware.display")
    fake_display.OLEDDisplay = object
    fake_rfid = types.ModuleType("hardware.rfid")
    fake_rfid.RFIDReader = object
    with patch.dict(sys.modules, {"hardware.display": fake_display, "hardware.rfid": fake_rfid}):
        return importlib.import_module("main")


class AttendanceDisplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = _load_main_with_fake_hardware()

    def test_already_recorded_is_successful_oled_feedback_not_an_error(self):
        display = Mock()
        result = AttendanceResult(
            success=True,
            student_name="Student 1",
            attendance_status="already_recorded_today",
        )
        with patch.object(self.application, "success_beep") as success_beep, patch.object(
            self.application, "error_beep"
        ) as error_beep:
            self.application._show_attendance_result(display, result)

        display.show_already_recorded.assert_called_once_with("Student 1")
        display.show_error.assert_not_called()
        success_beep.assert_called_once()
        error_beep.assert_not_called()

    def test_recorded_response_retains_existing_success_feedback(self):
        display = Mock()
        result = AttendanceResult(
            success=True,
            student_name="Student 1",
            attendance_status="recorded",
        )
        with patch.object(self.application, "success_beep"):
            self.application._show_attendance_result(display, result)

        display.show_success.assert_called_once_with("Student 1")

    def test_enrollment_card_is_not_sent_to_normal_attendance(self):
        application = self.application
        display = Mock()
        reader = Mock()
        reader.poll.side_effect = ["10-20-30-40", KeyboardInterrupt]
        pending = Enrollment(
            id=7,
            student_name="Student 1",
            student_number="ST001",
            expires_at=datetime(2026, 9, 6, 12, tzinfo=timezone.utc),
        )
        with patch.object(application, "OLEDDisplay", return_value=display), patch.object(
            application, "RFIDReader", return_value=reader
        ), patch.object(
            application, "load_device_aes_key", return_value=b"0123456789abcdef"
        ), patch.object(
            application,
            "poll_enrollment",
            side_effect=[
                EnrollmentPollResult("pending", pending),
                EnrollmentPollResult("none"),
            ],
        ), patch.object(
            application,
            "submit_enrollment_card",
            return_value=EnrollmentSubmitResult(True, "completed", student_name="Student 1"),
        ) as submit_enrollment, patch.object(
            application, "submit_attendance"
        ) as submit_attendance, patch.object(
            application, "_keep_removal_state_current"
        ), patch.object(application.signal, "signal"):
            assert application.run() == 0

        submit_enrollment.assert_called_once_with(7, "10-20-30-40")
        submit_attendance.assert_not_called()
        display.show_enrollment.assert_called_once_with("Student 1")
        display.show_card_registered.assert_called_once_with("Student 1")
