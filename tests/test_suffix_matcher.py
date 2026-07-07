"""P1: core/suffix_matcher.py 单元测试"""
import unittest
from core.types import SegType, ADMIN_SUFFIX_MAP
from core.suffix_matcher import find_suffix_boundaries


class TestFindSuffixBoundaries(unittest.TestCase):

    def test_basic_admin_split(self):
        boundaries = find_suffix_boundaries("北京市朝阳区", ADMIN_SUFFIX_MAP)
        ends = [(end, sfx, st.value) for end, start, sfx, st in boundaries]
        self.assertEqual(ends, [(3, "市", "CITY"), (6, "区", "DISTRICT")])

    def test_overlapping_keep_longer(self):
        boundaries = find_suffix_boundaries("海南省海口市", ADMIN_SUFFIX_MAP)
        ends = [(end, sfx, st.value) for end, start, sfx, st in boundaries]
        self.assertIn((3, "省", "PROVINCE"), ends)
        self.assertIn((6, "市", "CITY"), ends)

    def test_empty_text(self):
        boundaries = find_suffix_boundaries("", ADMIN_SUFFIX_MAP)
        self.assertEqual(boundaries, [])

    def test_no_match(self):
        boundaries = find_suffix_boundaries("abc123", ADMIN_SUFFIX_MAP)
        self.assertEqual(boundaries, [])

    def test_same_end_keep_longer_suffix(self):
        # "三河乡村" (4 chars): "乡" at 2→3 end=3, "乡村" at 2→4 end=4
        # start of "乡村"(2) < prev_end of "乡"(3) → overlap → keep longer
        test_map = {
            SegType.VILLAGE: {"乡", "乡村"},
        }
        boundaries = find_suffix_boundaries("三河乡村", test_map)
        ends = [(end, sfx, st.value) for end, start, sfx, st in boundaries]
        self.assertEqual(ends, [(4, "乡村", "VILLAGE")])

    def test_multiple_types(self):
        test_map = {
            SegType.CITY: {"市"},
            SegType.DISTRICT: {"区"},
        }
        boundaries = find_suffix_boundaries("杭州市西湖区文三路", test_map)
        ends = [(end, sfx, st.value) for end, start, sfx, st in boundaries]
        self.assertIn((3, "市", "CITY"), ends)
        self.assertIn((6, "区", "DISTRICT"), ends)


    def test_N9_deterministic_tie_break(self):
        """N9: same end + same length should be tie-broken by seg_type."""
        test_map = {
            SegType.CITY: {"市"},
            SegType.PROVINCE: {"省"},
        }
        boundaries = find_suffix_boundaries("浙江省杭州市", test_map)
        ends = [(end, sfx, st.value) for end, start, sfx, st in boundaries]
        self.assertIn((3, "省", "PROVINCE"), ends)
        self.assertIn((6, "市", "CITY"), ends)


if __name__ == "__main__":
    unittest.main()
