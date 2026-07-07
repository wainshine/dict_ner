"""P3/N22: pipeline.py + poi/recognizer.py 集成测试 (N5/N10回归)"""
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

    def test_recognize_returns_three_sections(self):
        r = self.pipe.recognize("北京市朝阳区")
        self.assertIn("text", r)
        self.assertIn("loc", r)
        self.assertIn("org", r)
        self.assertIn("poi", r)
        self.assertEqual(r["text"], "北京市朝阳区")

    def test_recognize_simple(self):
        out = self.pipe.recognize_simple("北京市朝阳区")
        self.assertIn("输入:", out)
        self.assertIn("地名:", out)

    def test_N5_poi_loads_correct_version(self):
        """N5: pipeline must load poi_v1.1.2, not v1.1.1."""
        self.assertEqual(
            self.pipe.poi._rec._dict_name, "poi_v1.1.2.pkl",
            "Pipeline should load current poi dict version"
        )

    def test_company_suffix_skips_poi(self):
        r = self.pipe.recognize("深圳市南山区华为技术有限公司")
        self.assertIsNone(r["poi"])

    def test_non_company_has_poi(self):
        r = self.pipe.recognize("峨眉山景区游客中心")
        self.assertIsNotNone(r["poi"])

    def test_N10_confidence_segment_level(self):
        """N10: confidence should be per-segment, not position-dependent."""
        r = self.pipe.recognize("北京市朝阳区")
        loc_segs = r["loc"]["segments"]
        if len(loc_segs) >= 2:
            # "北京市" (first seg) and "朝阳区" (second seg)
            # Both should have reasonable confidence (>0.1), not position-penalized
            for s in loc_segs:
                self.assertGreater(s["confidence"], 0.1,
                    f"Segment {s['text']} confidence too low: {s['confidence']}")


class TestPoiRecognizer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.poi = PoiRecognizer(DATA_DIR, dict_name="poi_v1.1.2.pkl")

    def test_recognize_poi_splits(self):
        res = self.poi.recognize("星巴克咖啡国贸店")
        self.assertGreater(len(res.segments), 0)

    def test_recognize_address(self):
        res = self.poi.recognize("北京市朝阳区")
        types = [s.seg_type.value for s in res.segments]
        self.assertIn("CITY", types)
        self.assertIn("DISTRICT", types)


if __name__ == "__main__":
    unittest.main()
