"""P2/N22: brand/model.py 品牌模型回归测试 (行为验证)"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from v2.brand_model import BrandModel

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DICT_DIR = os.path.join(BASE, "dicts")
VERSION = "v1.1.2"


def load_model():
    model = BrandModel(DICT_DIR, version=VERSION)
    if not model.load():
        raise unittest.SkipTest("brand model not found")
    return model


class TestBrandModel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.model = load_model()

    def test_load_success(self):
        self.assertGreater(len(self.model.bigram_counts), 100000)
        self.assertGreater(len(self.model.unigram_counts), 1000)

    def test_bigram_prob_bounds(self):
        prob = self.model.bigram_prob("华", "为")
        self.assertGreater(prob, 0)
        self.assertLess(prob, 1.0)

    def test_brand_score_behavior(self):
        brand = self.model.brand_score("字节跳动")
        short = self.model.brand_score("华为")
        suffix = self.model.brand_score("有限公司")
        single = self.model.brand_score("华")
        self.assertGreater(brand, 0.001)
        self.assertLess(suffix, brand,
            "Company suffix should score lower than real brand")
        self.assertGreater(single, 0.1,
            "Single char with model should not return hardcoded 0.3")

    def test_log_brand_score_negative(self):
        log_score = self.model.log_brand_score("华为")
        self.assertLess(log_score, 0)

    def test_empty_model_returns_neutral(self):
        m = BrandModel("/tmp", version="test_empty")
        m.total_bigrams = 0
        self.assertEqual(m.brand_score("华为"), 0.5)

    def test_save_and_reload(self):
        import tempfile, shutil
        tmpdir = tempfile.mkdtemp()
        try:
            model2 = BrandModel(tmpdir, version="test")
            model2.bigram_counts = self.model.bigram_counts
            model2.unigram_counts = self.model.unigram_counts
            model2.total_bigrams = self.model.total_bigrams
            model2.smoothing = self.model.smoothing
            model2.save()

            model3 = BrandModel(tmpdir, version="test")
            self.assertTrue(model3.load())
            self.assertEqual(model3.total_bigrams, self.model.total_bigrams)
            self.assertEqual(model3.smoothing, self.model.smoothing)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
