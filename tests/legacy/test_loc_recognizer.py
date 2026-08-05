"""P2/N22: loc/recognizer.py 地名识别回归测试 (精确断言)"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.types import SegType, AddressResult
from v2.loc_builder import DictBuilder
from v2.loc_recognizer import AddressRecognizer

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DICT_DIR = os.path.join(BASE, "dicts")
DICT_VERSION = "loc_v1.1.2"


def load_recognizer():
    b = DictBuilder.load(DICT_DIR, DICT_VERSION)
    return AddressRecognizer(b.dict_data)


class TestLocRecognition(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rec = load_recognizer()

    def _seg_full(self, text):
        """Return (type, text, start, end) tuples for precise assertion."""
        res = self.rec.recognize(text)
        return [(s.seg_type.value, s.text, s.start, s.end) for s in res.segments]

    def test_city_district_full(self):
        segs = self._seg_full("深圳市南山区")
        self.assertEqual(segs, [
            ("CITY", "深圳市", 0, 3),
            ("DISTRICT", "南山区", 3, 6),
        ])

    def test_province_city_district_full(self):
        segs = self._seg_full("陕西省安康市旬阳县")
        self.assertEqual(segs, [
            ("PROVINCE", "陕西省", 0, 3),
            ("CITY", "安康市", 3, 6),
            ("DISTRICT", "旬阳县", 6, 9),
        ])

    def test_city_district_road_full(self):
        segs = self._seg_full("杭州市西湖区文三路")
        self.assertEqual(segs, [
            ("CITY", "杭州市", 0, 3),
            ("DISTRICT", "西湖区", 3, 6),
            ("ROAD", "文三路", 6, 9),
        ])

    def test_address_poi_separation(self):
        segs = self._seg_full("深圳市南山区华为技术有限公司")
        types = [t for t, _, _, _ in segs]
        self.assertIn("CITY", types)
        self.assertIn("DISTRICT", types)
        self.assertIn("POI", types)
        # Address comes before POI
        addr_end = max(e for t, _, _, e in segs if t in ("CITY", "DISTRICT"))
        poi_start = min(s for t, _, s, _ in segs if t == "POI")
        self.assertLessEqual(addr_end, poi_start)

    def test_no_cross_contamination(self):
        """N1/N6: stop chars should not leak into segments."""
        segs = self._seg_full("北京市朝阳区")
        for t, text, _, _ in segs:
            self.assertFalse(any(ch in text for ch in "，。；、！？："))

    def test_to_dict_roundtrip(self):
        res = self.rec.recognize("北京市")
        d = res.to_dict()
        self.assertEqual(d["original"], "北京市")
        for s in d["segments"]:
            self.assertIn("text", s)
            self.assertIn("type", s)
            self.assertIn("confidence", s)
            self.assertIsInstance(s["confidence"], float)

    def test_empty_text_returns_empty(self):
        res = self.rec.recognize("")
        self.assertEqual(len(res.segments), 0)
        self.assertFalse(res.is_valid)

    def test_recognize_returns_address_result(self):
        res = self.rec.recognize("北京市朝阳区")
        self.assertIsInstance(res, AddressResult)
        self.assertGreater(len(res.segments), 0)


if __name__ == "__main__":
    unittest.main()
