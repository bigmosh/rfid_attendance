"""Temporary local student lookup.

This module deliberately has no knowledge of GPIO, SPI, I2C, or the OLED.
The dictionary can later be replaced by a backend lookup without changing the
hardware modules or the application coordinator.
"""

TEMPORARY_STUDENTS = {
    "77-48-28-61-92": "Student 1",
    "51-164-2-51-166": "Student 2",
}


def find_student(uid):
    """Return the temporary student name for ``uid``, or ``None`` if unknown."""
    return TEMPORARY_STUDENTS.get(uid)
