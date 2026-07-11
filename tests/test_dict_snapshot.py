"""N23: dict snapshot regression test — catches dict corruption/rebuild failures"""
import os
import sys
import pickle
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import SegType
from loc.builder import DictBuilder

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_DIR = os.path.join(BASE, "dicts")
LOC_VERSION = "v1.2.3"
ORG_VERSION = "v1.2.2"
POI_VERSION = "v1.2.2"
BRAND_VERSION = "v1.2.2"


class TestDictSnapshot(unittest.TestCase):
    """Verify that dictionaries have minimum expected sizes."""

    def test_loc_dict_total_words(self):
        b = DictBuilder.load(DICT_DIR, f"loc_{LOC_VERSION}")
        total = sum(len(v) for v in b.dict_data.values())
        self.assertGreater(total, 1_000_000,
            f"loc dict should have >1M words, got {total:,}")

    def test_loc_poi_not_empty(self):
        b = DictBuilder.load(DICT_DIR, f"loc_{LOC_VERSION}")
        poi_count = len(b.dict_data.get(SegType.POI, {}))
        self.assertGreater(poi_count, 10_000,
            f"loc POI should have >10K entries, got {poi_count:,}")

    def test_org_dict_has_core_suffixes(self):
        with open(os.path.join(DICT_DIR, f"org_{ORG_VERSION}.pkl"), "rb") as f:
            org = pickle.load(f)
        d4 = org.get("d4_freqs", {})
        for sfx in ["有限公司", "分公司", "公司", "集团"]:
            self.assertIn(sfx, d4,
                f"Core suffix '{sfx}' missing from org d4")

    def test_org_dict_entry_counts(self):
        with open(os.path.join(DICT_DIR, f"org_{ORG_VERSION}.pkl"), "rb") as f:
            org = pickle.load(f)
        self.assertGreater(len(org.get("d1_freqs", {})), 50_000)
        self.assertGreater(len(org.get("d3_freqs", {})), 15_000)
        self.assertGreater(len(org.get("d4_freqs", {})), 5_000)

    def test_poi_dict_has_core_suffixes(self):
        with open(os.path.join(DICT_DIR, f"poi_{POI_VERSION}.pkl"), "rb") as f:
            poi = pickle.load(f)
        d4 = poi.get("d4_freqs", {})
        for sfx in ["超市", "停车场", "银行", "宾馆"]:
            self.assertIn(sfx, d4,
                f"Core POI suffix '{sfx}' missing from poi d4")

    def test_brand_model_size(self):
        with open(os.path.join(DICT_DIR, f"brand_{BRAND_VERSION}.pkl"), "rb") as f:
            brand = pickle.load(f)
        self.assertGreater(len(brand.get("bigram_counts", {})), 500_000)
        self.assertGreater(brand.get("total_bigrams", 0), 100_000_000)


if __name__ == "__main__":
    unittest.main()
