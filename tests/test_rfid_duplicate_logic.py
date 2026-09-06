"""RC522 duplicate handling tests with a fake library object, not real hardware."""

import sys
import types
import unittest
from unittest.mock import patch


class _FakeRFID:
    def __init__(self, *args, **kwargs):
        self.request_results = []
        self.anticoll_results = []
        self.cleaned_up = False

    def request(self):
        return self.request_results.pop(0)

    def anticoll(self):
        return self.anticoll_results.pop(0)

    def cleanup(self):
        self.cleaned_up = True


class RFIDDuplicateLogicTests(unittest.TestCase):
    def test_held_card_is_returned_once_then_becomes_eligible_after_removal(self):
        fake_module = types.ModuleType("pirc522")
        fake_module.RFID = _FakeRFID
        with patch.dict(sys.modules, {"pirc522": fake_module}):
            from hardware.rfid import RFIDReader

            reader = RFIDReader()
            reader._reader.request_results = [(False, None), (False, None), (True, None), (False, None)]
            reader._reader.anticoll_results = [
                (False, [77, 48, 28, 61, 92]),
                (False, [77, 48, 28, 61, 92]),
                (False, [77, 48, 28, 61, 92]),
            ]

            assert reader.poll() == "77-48-28-61-92"
            assert reader.poll() is None
            assert reader.poll() is None
            assert reader.poll() == "77-48-28-61-92"
            reader.cleanup()
            assert reader._reader.cleaned_up is True
