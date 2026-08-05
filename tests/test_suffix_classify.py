"""core/suffix_classify.py 直测 — POI 后缀分类 (V1.1 从 loc/importer.py 提取)"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.suffix_classify import classify_suffix, _SAFE_SINGLE_SUFFIXES


class TestClassifySuffix(unittest.TestCase):
    def test_multi_char_suffixes(self):
        self.assertEqual(classify_suffix("人民医院"), "医院")
        self.assertEqual(classify_suffix("北京大学"), "学校")
        self.assertEqual(classify_suffix("希尔顿酒店"), "酒店")
        self.assertEqual(classify_suffix("国贸购物中心"), "商场")

    def test_safe_single_char(self):
        self.assertEqual(classify_suffix("啤酒厂"), "工业")
        self.assertEqual(classify_suffix("便利店"), "商业")

    def test_ambiguous_single_char_rejected(self):
        # 会/委/庭 等非安全单字后缀不分类, 兜底建筑
        self.assertNotEqual(classify_suffix("测试会"), "政府")
        self.assertNotEqual(classify_suffix("工会"), "政府")
        self.assertEqual(classify_suffix("测试会"), "建筑")

    def test_long_text_single_char_not_applied(self):
        # 单字后缀仅对 len<=3 生效; 长串不命中单字 "厂"
        self.assertEqual(classify_suffix("电机制造"), "工业")  # "制造" 2字命中
        self.assertEqual(classify_suffix("某某汽车制造厂"), "建筑")  # len>3, "厂" 不适用

    def test_default_fallback(self):
        self.assertEqual(classify_suffix("某某大厦"), "建筑")
        self.assertEqual(classify_suffix("奇特兹"), "建筑")

    def test_safe_set_frozen(self):
        self.assertEqual(_SAFE_SINGLE_SUFFIXES, {"厂", "店", "站", "园", "局", "院"})


if __name__ == "__main__":
    unittest.main()
