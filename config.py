"""Small collection of settings for the Raspberry Pi application."""

import os

OLED_WIDTH = 128
OLED_HEIGHT = 64
OLED_I2C_ADDRESS = 0x3C

# RC522 pin numbers are interpreted by pirc522 using BOARD numbering.
RC522_RESET_PIN = 22
RC522_IRQ_PIN = None

DISPLAY_RESULT_SECONDS = 2
RFID_POLL_INTERVAL_SECONDS = 0.1

# Backend connection settings. Configure production values through the Pi
# environment; no API URL or credentials are hardcoded in application logic.
API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "https://attendance.example.invalid",
).rstrip("/")
DEVICE_ID = os.getenv("DEVICE_ID", "attendance-pi-01")

try:
    REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "5"))
except ValueError:
    REQUEST_TIMEOUT_SECONDS = 5.0

try:
    ENROLLMENT_POLL_SECONDS = float(os.getenv("ENROLLMENT_POLL_SECONDS", "3"))
except ValueError:
    ENROLLMENT_POLL_SECONDS = 3.0
