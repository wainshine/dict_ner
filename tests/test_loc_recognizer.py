"""P2: loc/recognizer.py 地名识别 回归测试 (需要真实词典)"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import SegType
from loc.builder import DictBuilder
from loc.recognizer import AddressRecognizer

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_DIR = os.path.join(BASE, "dicts")
DICT_VERSION = "loc_v1.1.2"


def load_recognizer():
    b = DictBuilder.load(DICT_DIR, DICT_VERSION)
    return AddressRecognizer(b.dict_data)


class TestLocRecognition(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rec = load_recognizer()

    def _seg_types(self, text):
        res = self.rec.recognize(text)
        return [(s.seg_type.value, s.text) for s in res.segments]

    def test_city_district(self):
        segs = self._seg_types("深圳市南山区")
        self.assertEqual(segs, [
            ("CITY", "深圳市"),
            ("DISTRICT", "南山区"),
        ])

    def test_province_city_district(self):
        segs = self._seg_types("陕西省安康市旬阳县")
        self.assertEqual(segs, [
            ("PROVINCE", "陕西省"),
            ("CITY", "安康市"),
            ("DISTRICT", "旬阳县"),
        ])

    def test_city_district_road(self):
        segs = self._seg_types("杭州市西湖区文三路")
        self.assertEqual(segs, [
            ("CITY", "杭州市"),
            ("DISTRICT", "西湖区"),
            ("ROAD", "文三路"),
        ])

    def test_full_address_with_poi(self):
        segs = self._seg_types("深圳市南山区华为技术有限公司")
        types = [t for t, _ in segs]
        self.assertIn("CITY", types)
        self.assertIn("DISTRICT", types)
        self.assertIn("POI", types)

    def test_poi_only(self):
        segs = self._seg_types("星巴克咖啡")
        types = [t for t, _ in segs]
        self.assertTrue(all(t == "POI" or t == "UNKNOWN" for t in types))

    def test_orientation_in_address(self):
        segs = self._seg_types("北京市东城区北门")
        types = [t for t, _ in segs]
        self.assertIn("CITY", types)
        self.assertIn("DISTRICT", types)

    def test_empty_text(self):
        res = self.rec.recognize("")
        self.assertEqual(len(res.segments), 0)
        self.assertFalse(res.is_valid)

    def test_recognize_returns_address_segments(self):
        res = self.rec.recognize("北京市朝阳区")
        self.assertGreater(len(res.segments), 0)
        for seg in res.segments:
            self.assertIsInstance(seg.text, str)
            self.assertIsInstance(seg.seg_type, SegType)
            self.assertGreater(seg.end, seg.start)

    def test_to_dict_format(self):
        res = self.rec.recognize("北京市")
        d = res.to_dict()
        self.assertEqual(d["original"], "北京市")
        self.assertIsInstance(d["segments"], list)
        for s in d["segments"]:
            self.assertIn("text", s)
            self.assertIn("type", s)
            self.assertIn("confidence", s)


if __name__ == "__main__":
    unittest.main()
