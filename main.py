"""Application coordinator for Raspberry Pi RFID attendance."""

import logging
import sys
import time

from config import DISPLAY_RESULT_SECONDS, RFID_POLL_INTERVAL_SECONDS
from hardware.buzzer import error_beep, success_beep
from hardware.display import OLEDDisplay
from hardware.rfid import RFIDReader
from services.attendance import find_student


LOGGER = logging.getLogger(__name__)


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def run():
    """Run until Ctrl+C or an unrecoverable hardware error occurs."""
    display = None
    reader = None

    try:
        LOGGER.info("Application starting")
        display = OLEDDisplay()
        display.show_booting()

        reader = RFIDReader()
        display.show_ready()

        while True:
            uid = reader.poll()
            if uid is None:
                time.sleep(RFID_POLL_INTERVAL_SECONDS)
                continue

            LOGGER.info("Card detected")
            student_name = find_student(uid)

            if student_name is not None:
                LOGGER.info("Registered student detected: %s", student_name)
                display.show_success(student_name)
                success_beep()
            else:
                LOGGER.info("Unknown card detected")
                display.show_unknown()
                error_beep()

            _keep_removal_state_current(reader)
            display.show_ready()

    except KeyboardInterrupt:
        LOGGER.info("Ctrl+C received")
        return 0
    except Exception:
        LOGGER.exception("Hardware error")
        if display is not None:
            try:
                display.show_error("Hardware error")
            except Exception:
                LOGGER.exception("Unable to show hardware error on OLED")
        return 1
    finally:
        LOGGER.info("Application shutting down")
        if reader is not None:
            try:
                reader.cleanup()
            except Exception:
                LOGGER.exception("RFID cleanup failed")
        if display is not None:
            try:
                display.clear()
            except Exception:
                LOGGER.exception("OLED cleanup failed")


def _keep_removal_state_current(reader):
    """Poll for removal while the success or error screen remains visible."""
    deadline = time.monotonic() + DISPLAY_RESULT_SECONDS
    while time.monotonic() < deadline:
        reader.observe_removal()
        time.sleep(RFID_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    configure_logging()
    sys.exit(run())
