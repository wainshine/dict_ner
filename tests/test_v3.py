import os
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "models", "clf_v3.pkl")


class TestV3Features(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from v3.features import FeatureExtractor, FEATURE_NAMES
        cls.ex = FeatureExtractor()
        cls.names = FEATURE_NAMES

    def test_vector_shape(self):
        vec = self.ex.extract_vector("深圳市南山区华为技术有限公司")
        self.assertEqual(len(vec), len(self.names))

    def test_company_features(self):
        f = self.ex.extract("华为技术有限公司")
        self.assertEqual(f["has_comp"], 1.0)
        self.assertEqual(f["org_has_poi_terminal"], 1.0)
        self.assertGreater(f["d4_len"], 0)

    def test_addr_features(self):
        f = self.ex.extract("北京市朝阳区")
        self.assertGreater(f["loc_geo_cov"], 0.9)
        self.assertEqual(f["d4_len"], 0)

    def test_garbage_features(self):
        f = self.ex.extract("xyz123!!!")
        self.assertEqual(f["all_chinese"], 0.0)
        self.assertGreater(f["n_latin"], 0)

    def test_last_results_cached(self):
        self.ex.extract("北京市朝阳区")
        self.assertIsNotNone(self.ex.last_results)
        self.assertEqual(len(self.ex.last_results), 3)


@unittest.skipUnless(os.path.exists(MODEL_PATH), "v3 model not trained")
class TestV3Infer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from v3.infer import V3Classifier
        try:
            cls.clf = V3Classifier()
        except ImportError:
            raise unittest.SkipTest("sklearn not available")

    def assertCategory(self, text, expected):
        r = self.clf.classify(text)
        self.assertEqual(r["category"], expected,
                         f"classify({text!r}) -> {r['category']}, expected {expected}")

    def test_org_company(self):
        self.assertCategory("深圳市南山区华为技术有限公司", "ORG")

    def test_poi_store(self):
        self.assertCategory("海底捞火锅三里屯店", "POI")

    def test_poi_facility(self):
        self.assertCategory("XX停车场", "POI")

    def test_addr_admin(self):
        self.assertCategory("北京市朝阳区", "ADDR")

    def test_contract_keys(self):
        r = self.clf.classify("华为技术有限公司")
        for k in ("text", "category", "confidence", "best", "all"):
            self.assertIn(k, r)
        self.assertIn("ORG_SUFFIX", [s["type"] for s in r["best"]["segments"]])

    def test_empty(self):
        r = self.clf.classify("")
        self.assertEqual(r["category"], "UNKNOWN")

    def test_confidence_range(self):
        r = self.clf.classify("北京市朝阳区")
        self.assertGreaterEqual(r["confidence"], 0.0)
        self.assertLessEqual(r["confidence"], 1.0)

    def test_threaded_classify_no_cross_talk(self):
        """并发下 best/all 必须属于本次请求 (serve 线程池回归)。"""
        texts = [
            "北京市朝阳区星巴克咖啡国贸店",
            "麦当劳得来速餐厅",
            "深圳市南山区华为技术有限公司",
            "海底捞火锅三里屯店",
            "广州市天河区体育西路",
            "中国工商银行股份有限公司北京分行",
            "上海市浦东新区陆家嘴环路1000号",
            "杭州市西湖区北山街8号",
        ]

        def work(t):
            for _ in range(10):
                r = self.clf.classify(t)
                self.assertIsNotNone(r["best"])
                self.assertEqual(r["best"]["original"], t)
                joined = "".join(s["text"] for s in r["best"]["segments"])
                self.assertEqual(joined, t)

        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(work, texts * 4))


if __name__ == "__main__":
    unittest.main()
