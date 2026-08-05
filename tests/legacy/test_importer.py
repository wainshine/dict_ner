"""P1: loc/importer.py _split_admin + classify_suffix 单元测试"""
import unittest
from core.types import POI_SUFFIX_MAP
from v2.loc_importer import _split_admin, classify_suffix


class TestSplitAdmin(unittest.TestCase):

    def test_full_address(self):
        result = _split_admin("北京市朝阳区")
        expected = [("北京市", "CITY"), ("朝阳区", "DISTRICT")]
        self.assertEqual([(t, st.value) for t, st in result], expected)

    def test_province_city_district(self):
        result = _split_admin("陕西省安康市旬阳县")
        expected = [("陕西省", "PROVINCE"), ("安康市", "CITY"), ("旬阳县", "DISTRICT")]
        self.assertEqual([(t, st.value) for t, st in result], expected)

    def test_city_district(self):
        result = _split_admin("深圳市南山区")
        expected = [("深圳市", "CITY"), ("南山区", "DISTRICT")]
        self.assertEqual([(t, st.value) for t, st in result], expected)

    def test_province_city(self):
        result = _split_admin("浙江省杭州市")
        expected = [("浙江省", "PROVINCE"), ("杭州市", "CITY")]
        self.assertEqual([(t, st.value) for t, st in result], expected)

    def test_no_admin_suffix(self):
        result = _split_admin("星巴克咖啡")
        self.assertEqual(result, [])

    def test_empty(self):
        result = _split_admin("")
        self.assertEqual(result, [])


class TestClassifySuffix(unittest.TestCase):

    def test_hospital(self):
        self.assertEqual(classify_suffix("人民医院"), "医院")
        self.assertEqual(classify_suffix("社区卫生服务站"), "医院")

    def test_single_char_classify(self):
        """F1: short multi-char words with SAFE single-char suffix should match."""
        self.assertEqual(classify_suffix("啤酒厂"), "工业")
        self.assertEqual(classify_suffix("便利店"), "商业")

    def test_single_char_no_false_positive(self):
        """F1 negative: ambiguous single-char suffixes should NOT match multi-char inputs."""
        self.assertNotEqual(classify_suffix("测试会"), "政府")
        self.assertNotEqual(classify_suffix("工会"), "政府")
        self.assertEqual(classify_suffix("测试会"), "建筑")

    def test_long_words_block_single_char(self):
        """N16: words >3 chars should not be classified by single-char suffix."""
        self.assertEqual(classify_suffix("电机制造"), "工业")  # matched by "制造"(2-char)

    def test_school(self):
        self.assertEqual(classify_suffix("北京大学"), "学校")
        self.assertEqual(classify_suffix("第一中学"), "学校")

    def test_hotel(self):
        self.assertEqual(classify_suffix("希尔顿酒店"), "酒店")
        self.assertEqual(classify_suffix("如家旅馆"), "酒店")

    def test_mall(self):
        self.assertEqual(classify_suffix("国贸购物中心"), "商场")
        self.assertEqual(classify_suffix("华润超市"), "商场")

    def test_default_architecture(self):
        self.assertEqual(classify_suffix("某某大厦"), "建筑")

    def test_unknown_falls_back(self):
        self.assertEqual(classify_suffix("奇特兹"), "建筑")


if __name__ == "__main__":
    unittest.main()
