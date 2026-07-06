"""P2: brand/model.py 品牌模型 回归测试 (需要真实模型)"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brand.model import BrandModel

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

    def test_bigram_prob(self):
        prob = self.model.bigram_prob("华", "为")
        self.assertGreater(prob, 0)
        self.assertLess(prob, 1.0)

    def test_brand_score_known_brand(self):
        score = self.model.brand_score("字节跳动")
        self.assertGreater(score, 0.001)

    def test_brand_score_short(self):
        score = self.model.brand_score("有限公司")
        self.assertLess(score, 0.01)

    def test_brand_score_single_char(self):
        score = self.model.brand_score("华")
        self.assertAlmostEqual(score, 0.3, places=1)

    def test_log_brand_score(self):
        log_score = self.model.log_brand_score("华为")
        self.assertLess(log_score, 0)

    def test_save_and_reload(self):
        import tempfile
        tmpdir = tempfile.mkdtemp()
        try:
            model2 = BrandModel(tmpdir, version="test")
            model2.bigram_counts = self.model.bigram_counts
            model2.unigram_counts = self.model.unigram_counts
            model2.total_bigrams = self.model.total_bigrams
            model2.save()

            model3 = BrandModel(tmpdir, version="test")
            self.assertTrue(model3.load())
            self.assertEqual(model3.total_bigrams, self.model.total_bigrams)
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
