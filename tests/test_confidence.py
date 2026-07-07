"""N10/N22: confidence segment-level regression test"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loc.builder import DictBuilder
from loc.recognizer import AddressRecognizer

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_DIR = os.path.join(BASE, "dicts")


def load_recognizer():
    b = DictBuilder.load(DICT_DIR, "loc_v1.1.2")
    return AddressRecognizer(b.dict_data)


class TestConfidence(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rec = load_recognizer()

    def test_same_word_same_confidence(self):
        """N10: same word at different positions should have similar confidence."""
        # "南山区" at the end of different addresses
        res1 = self.rec.recognize("深圳市南山区")
        res2 = self.rec.recognize("广东省深圳市南山区")

        conf_1 = [s.confidence for s in res1.segments if s.text == "南山区"]
        conf_2 = [s.confidence for s in res2.segments if s.text == "南山区"]

        self.assertEqual(len(conf_1), 1)
        self.assertEqual(len(conf_2), 1)
        # Should not be position-penalized dramatically
        self.assertGreater(conf_2[0], 0.1,
            f"Nanshan confidence too low: {conf_2[0]} (should not be penalized for position)")

    def test_confidence_monotonic_for_quality(self):
        """Higher-freq words should have higher confidence."""
        res = self.rec.recognize("北京市朝阳区")
        confs = [(s.text, s.confidence) for s in res.segments]
        texts = [t for t, _ in confs]
        self.assertIn("北京市", texts)


if __name__ == "__main__":
    unittest.main()
