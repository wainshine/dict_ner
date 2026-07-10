import unittest
import sys
import os
import pickle

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DICT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dicts")


class TestD4Map(unittest.TestCase):
    def setUp(self):
        path = os.path.join(DICT_DIR, "d4_category_map.pkl")
        with open(path, "rb") as f:
            self.d4_map = pickle.load(f)

    def test_map_not_empty(self):
        self.assertGreater(len(self.d4_map), 5000)

    def test_company_suffix_is_org(self):
        entry = self.d4_map.get("有限公司")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["category"], "ORG")

    def test_parking_is_poi_fac(self):
        entry = self.d4_map.get("停车场")
        if entry:
            self.assertEqual(entry["category"], "POI_FAC")

    def test_all_categories_valid(self):
        valid = {"ORG", "POI_FAC", "POI_STORE", "ADDR", "AMBIGUOUS", "UNKNOWN"}
        for sfx, entry in self.d4_map.items():
            self.assertIn(entry["category"], valid, f"d4={sfx}")
