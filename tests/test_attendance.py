"""Tests for hardware-independent attendance logic only."""

import unittest

from services.attendance import find_student


class FindStudentTests(unittest.TestCase):
    def test_returns_student_1_for_first_temporary_uid(self):
        self.assertEqual(find_student("77-48-28-61-92"), "Student 1")

    def test_returns_student_2_for_second_temporary_uid(self):
        self.assertEqual(find_student("51-164-2-51-166"), "Student 2")

    def test_returns_none_for_unknown_uid(self):
        self.assertIsNone(find_student("1-2-3-4-5"))


if __name__ == "__main__":
    unittest.main()
