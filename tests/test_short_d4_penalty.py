"""N17: short-d4 penalty branch coverage test"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from org.recognizer import OrgDPRecognizer
from core.types import SegType

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "data")


class TestShortD4Penalty(unittest.TestCase):
    """Verify short-d4 penalty toggle is correctly wired and doesn't crash."""

    @classmethod
    def setUpClass(cls):
        cls.rec_penalty = OrgDPRecognizer(DATA_DIR, version="v1.1.2",
                                           disable_short_d4_penalty=False)
        cls.rec_no_penalty = OrgDPRecognizer(DATA_DIR, version="v1.1.2",
                                              disable_short_d4_penalty=True,
                                              allow_adjacent_d4=True)

    def test_flag_set_correctly(self):
        self.assertFalse(self.rec_penalty._disable_short_d4_penalty)
        self.assertTrue(self.rec_no_penalty._disable_short_d4_penalty)

    def test_both_recognize_without_crash(self):
        for rec in [self.rec_penalty, self.rec_no_penalty]:
            res = rec.recognize("深圳南山区科技园")
            self.assertGreater(len(res.segments), 0)

    def test_penalty_toggle_produces_valid_output(self):
        text = "深圳市南山区"
        res_p = self.rec_penalty.recognize(text)
        res_np = self.rec_no_penalty.recognize(text)
        self.assertGreater(len(res_p.segments), 0)
        self.assertGreater(len(res_np.segments), 0)

    def test_short_d4_words_exist(self):
        # Verify that at least some 2-3 char d4 entries exist
        suffixes = self.rec_penalty.d4_suffixes
        short = [s for s in suffixes if 2 <= len(s) <= 3]
        self.assertGreater(len(short), 0,
            f"Should have 2-3 char d4 entries, found {len(short)}")


if __name__ == "__main__":
    unittest.main()
