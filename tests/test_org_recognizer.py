"""P2: org/recognizer.py 机构名识别 回归测试 (需要真实词典)"""
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

    def _seg_types(self, text):
        res = self.rec.recognize(text)
        return [(s.seg_type.value, s.text) for s in res.segments]

    def test_standard_company(self):
        segs = self._seg_types("深圳市南山区华为技术有限公司")
        types = [t for t, _ in segs]
        self.assertIn("POI", types)
        self.assertIn("BRAND", types)

    def test_brand_tech_company(self):
        segs = self._seg_types("字节跳动科技有限公司")
        types = [t for t, _ in segs]
        self.assertIn("BRAND", types)
        self.assertIn("POI", types)

    def test_four_level_address_company(self):
        segs = self._seg_types("陕西省安康市旬阳县XX公司")
        types = [t for t, _ in segs]
        self.assertIn("PROVINCE", types)
        self.assertIn("CITY", types)
        self.assertIn("DISTRICT", types)

    def test_multi_suffix_org(self):
        segs = self._seg_types("中国工商银行股份有限公司北京分行")
        types = [t for t, _ in segs]
        self.assertIn("POI", types)

    def test_scenic_spot(self):
        segs = self._seg_types("峨眉山景区游客中心")
        types = [t for t, _ in segs]
        self.assertIn("INDUSTRY", types)

    def test_empty_text(self):
        res = self.rec.recognize("")
        self.assertEqual(len(res.segments), 0)

    def test_brand_score(self):
        score_huawei = self.rec.brand_score("华为")
        score_ltd = self.rec.brand_score("有限公司")
        self.assertGreater(score_huawei, 0)
        self.assertLess(score_huawei, 1.0)
        self.assertLess(score_ltd, 0.1)  # company suffix should have low brand score

    def test_d4_suffixes_exist(self):
        suffixes = self.rec.d4_suffixes
        self.assertGreater(len(suffixes), 100)
        self.assertIn("有限公司", suffixes)

    def test_d3_words_exist(self):
        words = self.rec.d3_words
        self.assertGreater(len(words), 100)


if __name__ == "__main__":
    unittest.main()
