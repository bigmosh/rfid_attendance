"""Tests for hardware-independent attendance result types only."""

import unittest

from services.attendance import AttendanceResult


class AttendanceResultTests(unittest.TestCase):
    def test_success_result_carries_student_and_attendance_data(self):
        result = AttendanceResult(
            success=True,
            student_name="Student 1",
            student_number="ST001",
            attendance_id=1,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.student_name, "Student 1")
        self.assertEqual(result.attendance_id, 1)

    def test_failure_result_carries_a_reason(self):
        result = AttendanceResult(success=False, reason="unknown_card")

        self.assertFalse(result.success)
        self.assertEqual(result.reason, "unknown_card")


if __name__ == "__main__":
    unittest.main()
