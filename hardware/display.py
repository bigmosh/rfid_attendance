"""SSD1306 OLED display operations."""

import logging

import board
import busio
import adafruit_ssd1306
from PIL import Image, ImageDraw, ImageFont

from config import OLED_HEIGHT, OLED_I2C_ADDRESS, OLED_WIDTH


LOGGER = logging.getLogger(__name__)


class OLEDDisplay:
    """Render the small set of screens used by the attendance application."""

    def __init__(self):
        i2c = busio.I2C(board.SCL, board.SDA)
        self._oled = adafruit_ssd1306.SSD1306_I2C(
            OLED_WIDTH,
            OLED_HEIGHT,
            i2c,
            addr=OLED_I2C_ADDRESS,
        )
        self._font = ImageFont.load_default()
        self.clear()
        LOGGER.info("OLED initialized")

    def clear(self):
        """Clear all pixels on the display."""
        self._oled.fill(0)
        self._oled.show()

    def show_booting(self):
        self._show_lines("ATTENDANCE", "Starting...")

    def show_ready(self):
        self._show_lines("ATTENDANCE", "SYSTEM READY", "", "Tap your card")

    def show_success(self, student_name):
        self._show_lines("WELCOME", student_name, "", "Attendance OK")

    def show_unknown(self):
        self._show_lines("UNKNOWN CARD", "", "Not registered")

    def show_error(self, message):
        self._show_lines("ERROR", message)

    def show_enrollment(self, student_name):
        """Show that the next RFID card is reserved for registration."""
        self._show_lines("REGISTER CARD", student_name, "", "Tap new card...")

    def show_card_registered(self, student_name):
        self._show_lines("CARD REGISTERED", student_name)

    def show_card_in_use(self):
        self._show_lines("CARD IN USE", "", "Try another card")

    def show_enrollment_expired(self):
        self._show_lines("REGISTRATION", "EXPIRED")

    def show_enrollment_cancelled(self):
        self._show_lines("REGISTRATION", "CANCELLED")

    def show_enrollment_failed(self):
        self._show_lines("REGISTRATION", "FAILED")

    def show_network_error(self):
        self._show_lines("NETWORK ERROR", "", "Try again")

    def _show_lines(self, *lines):
        image = Image.new("1", (OLED_WIDTH, OLED_HEIGHT))
        draw = ImageDraw.Draw(image)

        y_position = 0
        for line in lines:
            # The default bitmap font fits about 21 characters on a 128px OLED.
            draw.text((0, y_position), str(line)[:21], font=self._font, fill=255)
            y_position += 16

        self._oled.image(image)
        self._oled.show()
