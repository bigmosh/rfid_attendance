"""RC522 polling and duplicate-scan handling."""

import logging

from config import RC522_IRQ_PIN, RC522_RESET_PIN


LOGGER = logging.getLogger(__name__)


class RFIDReader:
    """Read one UID per card placement using the RC522 polling API."""

    def __init__(self):
        # Import here so attendance-service tests do not require Pi hardware packages.
        from pirc522 import RFID

        # pin_rst is intentionally BOARD pin 22 (physical pin 22 / GPIO25).
        # IRQ is not wired, so detection must use request() polling.
        self._reader = RFID(pin_rst=RC522_RESET_PIN, pin_irq=RC522_IRQ_PIN)
        self._active_uid = None
        LOGGER.info("RFID reader initialized")

    def poll(self):
        """Return a newly placed card UID, or ``None`` when there is no new card.

        A UID is returned once while that card remains on the reader. A failed
        request means no card is present, which resets the duplicate-scan state
        and makes the card eligible again after it is removed and re-tapped.
        """
        error, _tag_type = self._reader.request()
        if error:
            if self._active_uid is not None:
                LOGGER.info("Card removed")
            self._active_uid = None
            return None

        error, uid = self._reader.anticoll()
        if error:
            LOGGER.debug("RFID anti-collision read failed")
            return None

        uid_string = "-".join(str(value) for value in uid)
        if uid_string == self._active_uid:
            return None

        self._active_uid = uid_string
        LOGGER.info("UID detected: %s", uid_string)
        return uid_string

    def observe_removal(self):
        """Update duplicate-scan state while another screen is being shown.

        This intentionally only calls ``request()``. It watches for the card
        leaving the reader without treating a newly presented card as already
        processed.
        """
        error, _tag_type = self._reader.request()
        if error and self._active_uid is not None:
            LOGGER.info("Card removed")
            self._active_uid = None
            return True
        return False

    def cleanup(self):
        """Release any RC522 state used by the underlying library."""
        self._reader.cleanup()
        LOGGER.info("RFID reader cleaned up")
