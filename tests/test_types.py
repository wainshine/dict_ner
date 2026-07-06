"""P3: core/types.py 类型和常量 单元测试"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import (
    SegType, AddressSegment, AddressResult,
    LEVEL_ORDER, ADMIN_SUFFIX_MAP, LOCATION_SUFFIX_MAP, POI_SUFFIX_MAP,
)


class TestSegType(unittest.TestCase):

    def test_str_enum_values(self):
        self.assertEqual(SegType.PROVINCE.value, "PROVINCE")
        self.assertEqual(SegType.CITY.value, "CITY")
        self.assertEqual(SegType.POI.value, "POI")

    def test_level_order_has_all_admin_types(self):
        for st in [SegType.PROVINCE, SegType.CITY, SegType.DISTRICT,
                    SegType.TOWN, SegType.VILLAGE, SegType.COMMUNITY, SegType.ROAD]:
            self.assertIn(st, LEVEL_ORDER)

    def test_admin_suffix_map_has_seven_categories(self):
        self.assertIn(SegType.PROVINCE, ADMIN_SUFFIX_MAP)
        self.assertIn(SegType.CITY, ADMIN_SUFFIX_MAP)
        self.assertIn(SegType.DISTRICT, ADMIN_SUFFIX_MAP)
        self.assertIn(SegType.TOWN, ADMIN_SUFFIX_MAP)
        self.assertIn(SegType.VILLAGE, ADMIN_SUFFIX_MAP)
        self.assertIn(SegType.COMMUNITY, ADMIN_SUFFIX_MAP)
        self.assertIn(SegType.ROAD, ADMIN_SUFFIX_MAP)

    def test_location_suffix_not_empty(self):
        self.assertGreater(len(LOCATION_SUFFIX_MAP), 50)
        self.assertIn("对面", LOCATION_SUFFIX_MAP)

    def test_poi_suffix_loads_from_csv(self):
        self.assertGreater(len(POI_SUFFIX_MAP), 100)
        self.assertEqual(POI_SUFFIX_MAP.get("医院"), "医院")
        self.assertEqual(POI_SUFFIX_MAP.get("有限公司"), "商业")


class TestAddressSegment(unittest.TestCase):

    def test_create_segment(self):
        seg = AddressSegment(
            text="北京市", seg_type=SegType.CITY, start=0, end=3, confidence=0.9
        )
        self.assertEqual(seg.text, "北京市")
        self.assertEqual(seg.seg_type, SegType.CITY)
        self.assertEqual(seg.length, 3)

    def test_default_confidence(self):
        seg = AddressSegment(text="test", seg_type=SegType.UNKNOWN, start=0, end=4)
        self.assertEqual(seg.confidence, 1.0)


class TestAddressResult(unittest.TestCase):

    def test_empty_result(self):
        result = AddressResult(original="test")
        self.assertFalse(result.is_valid)

    def test_valid_result(self):
        seg = AddressSegment(text="北京市", seg_type=SegType.CITY, start=0, end=3)
        result = AddressResult(original="北京市", segments=[seg])
        self.assertTrue(result.is_valid)

    def test_to_dict(self):
        seg = AddressSegment(text="北京市", seg_type=SegType.CITY, start=0, end=3)
        result = AddressResult(original="北京市", segments=[seg])
        d = result.to_dict()
        self.assertEqual(d["original"], "北京市")
        self.assertEqual(len(d["segments"]), 1)
        self.assertEqual(d["segments"][0]["text"], "北京市")
        self.assertEqual(d["segments"][0]["type"], "CITY")


if __name__ == "__main__":
    unittest.main()
