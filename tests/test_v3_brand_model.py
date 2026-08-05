"""v3/brand_model.py 单元测试 — save/load 回环 + score 边界"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from v3.brand_model import BrandModel

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_DIR = os.path.join(BASE, "dicts")


def train_tiny(model):
    # 极简人工语料: 品牌词 vs 后缀词
    model.bigram_counts.update({"华为": 100, "为技": 80, "技术": 60,
                                "有限": 5, "限公": 5, "公司": 5})
    model.unigram_counts.update({"华": 100, "为": 180, "技": 80, "术": 60,
                                 "有": 5, "限": 10, "公": 5, "司": 5})
    model.total_bigrams = sum(model.bigram_counts.values())


class TestBrandModelV3(unittest.TestCase):
    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            m = BrandModel(d, version="test")
            train_tiny(m)
            m.save()
            m2 = BrandModel(d, version="test")
            self.assertTrue(m2.load())
            self.assertEqual(m2.total_bigrams, m.total_bigrams)
            self.assertEqual(m2.bigram_counts, m.bigram_counts)
            self.assertEqual(m2.unigram_counts, m.unigram_counts)

    def test_load_missing_returns_false(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(BrandModel(d, version="nonexist").load())

    def test_brand_score_bounds(self):
        m = BrandModel("/tmp", version="x")
        train_tiny(m)
        s_brand = m.brand_score("华为技术")
        s_suffix = m.brand_score("有限公司")
        self.assertGreater(s_brand, s_suffix)
        self.assertGreater(s_brand, 0)
        self.assertLess(s_brand, 1.0)

    def test_empty_model_score(self):
        m = BrandModel("/tmp", version="x")
        self.assertEqual(m.brand_score("任意文本"), 0.5)

    def test_single_char_score(self):
        m = BrandModel("/tmp", version="x")
        train_tiny(m)
        self.assertEqual(m.brand_score("华"), 0.3)


class TestBrandModelReal(unittest.TestCase):
    """真模型 (dicts/brand_v1.5.0.pkl) 冒烟"""
    @classmethod
    def setUpClass(cls):
        cls.m = BrandModel(DICT_DIR, version="v1.5.0")
        if not cls.m.load():
            raise unittest.SkipTest("brand_v1.5.0.pkl not found")

    def test_real_scores(self):
        self.assertGreater(self.m.brand_score("华为"),
                           self.m.brand_score("有限公司"))
        self.assertLess(self.m.brand_score("有限公司"), 0.03)


if __name__ == "__main__":
    unittest.main()
