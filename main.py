"""Application coordinator for Raspberry Pi RFID attendance."""

import logging
import signal
import sys
import time

from config import DISPLAY_RESULT_SECONDS, RFID_POLL_INTERVAL_SECONDS
from hardware.buzzer import error_beep, success_beep
from hardware.display import OLEDDisplay
from hardware.rfid import RFIDReader
from services.attendance import submit_attendance


LOGGER = logging.getLogger(__name__)


def _handle_shutdown_signal(_signum, _frame):
    """Use the existing cleanup path when systemd sends SIGTERM."""
    raise KeyboardInterrupt


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def run():
    """Run until Ctrl+C or an unrecoverable hardware error occurs."""
    display = None
    reader = None
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)

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
            attendance_result = submit_attendance(uid)

            if attendance_result.success:
                LOGGER.info("Attendance recorded")
                display.show_success(attendance_result.student_name)
                success_beep()
            elif attendance_result.reason == "unknown_card":
                LOGGER.info("Unknown card detected")
                display.show_unknown()
                error_beep()
            elif attendance_result.reason == "card_disabled":
                LOGGER.info("Disabled card detected")
                display.show_error("Card disabled")
                error_beep()
            elif attendance_result.reason == "student_inactive":
                LOGGER.info("Inactive student detected")
                display.show_error("Student inactive")
                error_beep()
            elif attendance_result.reason == "unknown_device":
                LOGGER.error("Device is not registered by backend")
                display.show_error("Device error")
                error_beep()
            elif attendance_result.reason == "network_error":
                LOGGER.warning("Attendance backend is unreachable")
                display.show_error("Network error")
                error_beep()
            else:
                LOGGER.error("Unexpected attendance backend response")
                display.show_error("Server error")
                error_beep()

            _keep_removal_state_current(reader)
            display.show_ready()

    except KeyboardInterrupt:
        LOGGER.info("Shutdown requested")
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
