import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline import DictNerPipeline


class TestClassify(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipe = DictNerPipeline()

    def assertCategory(self, text, expected):
        r = self.pipe.classify(text)
        self.assertEqual(r["category"], expected,
                         f"classify({text!r}) -> {r['category']}, expected {expected} "
                         f"(conf={r['confidence']})")

    def test_org_company(self):
        self.assertCategory("深圳市南山区华为技术有限公司", "ORG")

    def test_org_gov(self):
        self.assertCategory("广东省卫健委", "ORG")

    def test_poi_facility(self):
        self.assertCategory("XX停车场", "POI")

    def test_poi_store_road(self):
        self.assertCategory("XX黄河路店", "POI")

    def test_poi_store_geo(self):
        self.assertCategory("星巴克咖啡望京店", "POI")

    def test_addr_admin(self):
        self.assertCategory("北京市朝阳区", "ADDR")

    def test_addr_natural(self):
        self.assertCategory("西湖", "ADDR")

    def test_unknown_empty(self):
        self.assertCategory("", "UNKNOWN")

    def test_unknown_garbage(self):
        self.assertCategory("xyz123!!!", "UNKNOWN")

    def test_best_remap(self):
        r = self.pipe.classify("华为技术有限公司")
        types = [s["type"] for s in r["best"]["segments"]]
        self.assertIn("ORG_SUFFIX", types)

    def test_all_org_unchanged(self):
        r = self.pipe.classify("华为技术有限公司")
        types = [s["type"] for s in r["all"]["org"]["segments"]]
        self.assertIn("ORG_SUFFIX", types)

    def test_t_unknown_configurable(self):
        pipe = DictNerPipeline(t_unknown=0.99)
        r = pipe.classify("北京市朝阳区")
        self.assertEqual(r["category"], "UNKNOWN")
