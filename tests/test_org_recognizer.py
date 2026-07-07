"""P2/N22: org/recognizer.py 机构名识别回归测试 (精确断言 + N2/N5回归)"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import SegType
from org.recognizer import OrgDPRecognizer

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "data")
VERSION = "v1.1.2"


def load_recognizer():
    return OrgDPRecognizer(DATA_DIR, version=VERSION)


class TestOrgRecognition(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rec = load_recognizer()

    def _seg_full(self, text):
        res = self.rec.recognize(text)
        return [(s.seg_type.value, s.text) for s in res.segments]

    def test_standard_company_full(self):
        segs = self._seg_full("深圳市南山区华为技术有限公司")
        types = [t for t, _ in segs]
        self.assertIn("POI", types)
        self.assertIn("BRAND", types)
        # Company suffix must be POI
        self.assertEqual(segs[-1], ("POI", "有限公司"))

    def test_brand_tech_company_full(self):
        segs = self._seg_full("字节跳动科技有限公司")
        self.assertIn(("BRAND", "字节跳动"), segs)
        self.assertIn(("POI", "有限公司"), segs)

    def test_four_level_address_company_full(self):
        segs = self._seg_full("陕西省安康市旬阳县XX公司")
        types = [t for t, _ in segs]
        self.assertIn("PROVINCE", types)
        self.assertIn("CITY", types)
        self.assertIn("DISTRICT", types)
        self.assertIn("POI", types)

    def test_multi_suffix_org_full(self):
        segs = self._seg_full("中国工商银行股份有限公司北京分行")
        types = [t for t, _ in segs]
        self.assertIn("POI", types)
        self.assertIn("CITY", types)

    def test_N2_trailing_single_merge(self):
        """N2: TRAILING_SINGLE merge — 'XX咖啡档' (not in d4 trie) absorbs '档'."""
        segs = self._seg_full("XX咖啡档")
        self.assertEqual(segs, [("BRAND", "XX"), ("POI", "咖啡档")])

    def test_brand_score_bounds(self):
        score_huawei = self.rec.brand_score("华为")
        score_ltd = self.rec.brand_score("有限公司")
        self.assertGreater(score_huawei, 0)
        self.assertLess(score_huawei, 1.0)
        self.assertLess(score_ltd, 0.03, "Company suffix should have very low brand score")

    def test_d4_suffixes_content(self):
        suffixes = self.rec.d4_suffixes
        self.assertGreater(len(suffixes), 100)
        self.assertIn("有限公司", suffixes)

    def test_d3_words_content(self):
        words = self.rec.d3_words
        self.assertGreater(len(words), 100)

    def test_empty_text(self):
        res = self.rec.recognize("")
        self.assertEqual(len(res.segments), 0)


if __name__ == "__main__":
    unittest.main()
