"""Small collection of settings for the Raspberry Pi application."""

OLED_WIDTH = 128
OLED_HEIGHT = 64
OLED_I2C_ADDRESS = 0x3C

# RC522 pin numbers are interpreted by pirc522 using BOARD numbering.
RC522_RESET_PIN = 22
RC522_IRQ_PIN = None

DISPLAY_RESULT_SECONDS = 2
RFID_POLL_INTERVAL_SECONDS = 0.1
