"""Safe placeholder for the future buzzer hardware."""

import logging


LOGGER = logging.getLogger(__name__)


def success_beep():
    """Record where a success sound will be triggered once hardware is known."""
    LOGGER.info("Success beep requested (buzzer not configured)")


def error_beep():
    """Record where an error sound will be triggered once hardware is known."""
    LOGGER.info("Error beep requested (buzzer not configured)")
