"""N17/F12: short-d4 penalty branch coverage + on/off diff test"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from org.recognizer import OrgDPRecognizer
from core.types import SegType

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "data")


class TestShortD4Penalty(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rec_penalty = OrgDPRecognizer(DATA_DIR, version="v1.1.2",
                                           disable_short_d4_penalty=False)
        cls.rec_no_penalty = OrgDPRecognizer(DATA_DIR, version="v1.1.2",
                                              disable_short_d4_penalty=True,
                                              allow_adjacent_d4=True)

    def _types(self, rec, text):
        return [s.seg_type.value for s in rec.recognize(text).segments]

    def test_flag_wired_correctly(self):
        self.assertFalse(self.rec_penalty._disable_short_d4_penalty)
        self.assertTrue(self.rec_no_penalty._disable_short_d4_penalty)

    def test_both_modes_produce_output(self):
        for rec in [self.rec_penalty, self.rec_no_penalty]:
            res = rec.recognize("深圳南山区科技园")
            self.assertGreater(len(res.segments), 0)

    def test_penalty_on_off_diff(self):
        """F12: penalty toggle should produce different segment type sequences."""
        types_on = self._types(self.rec_penalty, "XY裁缝部AB科技园")
        types_off = self._types(self.rec_no_penalty, "XY裁缝部AB科技园")
        self.assertNotEqual(types_on, types_off,
            f"Penalty toggle should change output for known trigger text. "
            f"ON={types_on}, OFF={types_off}")


if __name__ == "__main__":
    unittest.main()
