"""v3/pipeline.py 单元测试 — 后处理方法 (合成段) + 三表懒加载 (真表只读)"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import SegType, AddressSegment, AddressResult
from v3.pipeline import V3Pipeline, COMPANY_SUFFIXES, GOV_SUFFIXES


def seg(text, stype, start=0):
    return AddressSegment(text=text, seg_type=stype, start=start,
                          end=start + len(text))


def bare_pipeline():
    # 跳过 __init__ 的重型引擎加载, 仅测纯方法与表加载器
    import threading
    p = object.__new__(V3Pipeline)
    p._lock = threading.Lock()
    p._d4_map = None
    p._suffix_table = None
    p._sql_suffixes = None
    return p


class TestConstants(unittest.TestCase):
    def test_company_suffixes(self):
        self.assertIn("有限公司", COMPANY_SUFFIXES)
        self.assertIn("股份有限公司", COMPANY_SUFFIXES)

    def test_gov_suffixes(self):
        self.assertIn("卫健委", GOV_SUFFIXES)
        self.assertIn("人民政府", GOV_SUFFIXES)


class TestPostProcessing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = bare_pipeline()

    def test_remap_poi_to_org_suffix(self):
        r = AddressResult(original="x", segments=[
            seg("华为", SegType.BRAND, 0), seg("店", SegType.POI, 2)])
        out = self.p._remap_org_segments(r)
        self.assertEqual(out.segments[0].seg_type, SegType.BRAND)
        self.assertEqual(out.segments[1].seg_type, SegType.ORG_SUFFIX)

    def test_remap_none_safe(self):
        self.assertIsNone(self.p._remap_org_segments(None))
        r = AddressResult(original="x", segments=[])
        self.assertEqual(self.p._remap_org_segments(r).segments, [])

    def test_has_company_suffix(self):
        r = AddressResult(original="x", segments=[seg("华为有限公司", SegType.POI, 0)])
        self.assertTrue(self.p._has_company_suffix(r))
        r2 = AddressResult(original="x", segments=[seg("星巴克咖啡", SegType.POI, 0)])
        self.assertFalse(self.p._has_company_suffix(r2))

    def test_detect_compound_mid(self):
        segs = [seg("华为", SegType.BRAND, 0), seg("有限公司", SegType.ORG_SUFFIX, 2),
                seg("阿里", SegType.BRAND, 6)]
        self.assertEqual(self.p._detect_compound(segs), 6)

    def test_detect_compound_last_is_none(self):
        segs = [seg("华为", SegType.BRAND, 0), seg("有限公司", SegType.ORG_SUFFIX, 2)]
        self.assertIsNone(self.p._detect_compound(segs))

    def test_detect_compound_non_company_suffix_ignored(self):
        segs = [seg("幸福", SegType.BRAND, 0), seg("便利店", SegType.ORG_SUFFIX, 2),
                seg("xx", SegType.BRAND, 5)]
        self.assertIsNone(self.p._detect_compound(segs))

    def test_merge_over_split(self):
        # "有限"+"公司" 合并后在 suffix 索引中 → 合并为 INDUSTRY
        segs = [seg("有限", SegType.INDUSTRY, 0), seg("公司", SegType.BRAND, 2)]
        out = self.p._merge_over_split(segs)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].text, "有限公司")
        self.assertEqual(out[0].seg_type, SegType.INDUSTRY)

    def test_merge_over_split_addr_protected(self):
        # 地址类型不参与合并
        segs = [seg("有限", SegType.CITY, 0), seg("公司", SegType.BRAND, 2)]
        out = self.p._merge_over_split(segs)
        self.assertEqual(len(out), 2)


class TestTableLoaders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = bare_pipeline()

    def test_d4_map(self):
        m = self.p.d4_map
        self.assertGreater(len(m), 8000)
        self.assertEqual(m["有限公司"]["category"], "ORG")

    def test_suffix_table(self):
        t = self.p.suffix_table
        self.assertGreater(len(t), 1000)
        self.assertEqual(t["公共厕所"], "POI_FAC")

    def test_sql_suffixes(self):
        s = self.p.sql_suffixes
        self.assertGreater(len(s), 20000)
        self.assertIn("有限公司", s)

    def test_loaders_cached(self):
        self.assertIs(self.p.d4_map, self.p.d4_map)
        self.assertIs(self.p.suffix_table, self.p.suffix_table)
        self.assertIs(self.p.sql_suffixes, self.p.sql_suffixes)


class TestReSplit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = V3Pipeline()  # 完整加载 (v1.5.0 引擎)

    def test_re_split_and_recognize(self):
        text = "华为有限公司阿里有限公司"
        r = self.p._re_split_and_recognize(text, 6)
        joined = "".join(s.text for s in r.segments)
        self.assertEqual(joined, text)
        # start/end 连续无断点
        for i, s in enumerate(r.segments):
            self.assertEqual(s.start, 0 if i == 0 else r.segments[i - 1].end)
            self.assertEqual(s.end, s.start + len(s.text))


if __name__ == "__main__":
    unittest.main()
