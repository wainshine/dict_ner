"""N17/F12: short-d4 penalty branch coverage test"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from org.recognizer import OrgDPRecognizer

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

    def test_flag_wired_correctly(self):
        self.assertFalse(self.rec_penalty._disable_short_d4_penalty)
        self.assertTrue(self.rec_no_penalty._disable_short_d4_penalty)

    def test_both_modes_produce_segments(self):
        for rec in [self.rec_penalty, self.rec_no_penalty]:
            res = rec.recognize("深圳南山区科技园")
            self.assertGreater(len(res.segments), 0)

    def test_short_d4_entries_exist(self):
        suffixes = self.rec_penalty.d4_suffixes
        short = [s for s in suffixes if 2 <= len(s) <= 3]
        self.assertGreater(len(short), 1000)

    def test_low_freq_d4_in_penalty_range(self):
        """Verify penalty-branch entry exists: 2-3 char, freq<50K in d4_freqs."""
        from core.types import SegType
        res = self.rec_penalty._find_matches("XX精剪屋")
        short_matches = [(s,e,t,f) for s,e,t,f in res
                         if t == SegType.POI and 2 <= (e-s) <= 3]
        self.assertGreater(len(short_matches), 0,
            "Should find 2-3 char POI matches for known low-freq d4 suffix")


if __name__ == "__main__":
    unittest.main()
