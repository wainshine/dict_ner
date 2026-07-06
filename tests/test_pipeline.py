"""P3: pipeline.py + poi/recognizer.py 集成测试 (需要真实词典)"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import DictNerPipeline
from poi.recognizer import PoiRecognizer

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "data")


class TestPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.pipe = DictNerPipeline(
            loc_dict="loc_v1.1.2",
            org_dict="v1.1.2",
            poi_dict="poi_v1.1.2",
        )

    def test_recognize_returns_three_keys(self):
        r = self.pipe.recognize("北京市朝阳区")
        self.assertIn("text", r)
        self.assertIn("loc", r)
        self.assertIn("org", r)
        self.assertIn("poi", r)

    def test_recognize_simple(self):
        out = self.pipe.recognize_simple("北京市朝阳区")
        self.assertIn("输入:", out)
        self.assertIn("地名:", out)

    def test_company_suffix_skips_poi(self):
        r = self.pipe.recognize("深圳市南山区华为技术有限公司")
        self.assertIsNone(r["poi"])

    def test_non_company_has_poi(self):
        r = self.pipe.recognize("峨眉山景区游客中心")
        self.assertIsNotNone(r["poi"])

    def test_has_company_suffix(self):
        r = self.pipe._has_company_suffix(
            self.pipe.org.recognize("XX有限公司")
        )
        self.assertTrue(r)

    def test_has_company_suffix_negative(self):
        r = self.pipe._has_company_suffix(
            self.pipe.org.recognize("星巴克咖啡")
        )
        self.assertFalse(r)


class TestPoiRecognizer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.poi = PoiRecognizer(DATA_DIR, dict_name="poi_v1.1.2.pkl")

    def test_recognize_poi(self):
        res = self.poi.recognize("星巴克咖啡国贸店")
        self.assertGreater(len(res.segments), 0)

    def test_recognize_address(self):
        res = self.poi.recognize("北京市朝阳区")
        segs = [(s.seg_type.value, s.text) for s in res.segments]
        types = [t for t, _ in segs]
        self.assertIn("CITY", types)
        self.assertIn("DISTRICT", types)


if __name__ == "__main__":
    unittest.main()
