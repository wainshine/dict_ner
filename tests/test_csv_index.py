import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.csv_index import CsvIndex


class TestCsvIndex(unittest.TestCase):
    def setUp(self):
        self.idx = CsvIndex.instance()

    def test_suffix_lookup_company(self):
        e = self.idx.lookup_suffix("有限公司")
        self.assertIsNotNone(e)

    def test_suffix_lookup_facility(self):
        e = self.idx.lookup_suffix("停车场")
        self.assertIsNotNone(e)
        self.assertGreater(e.loc_ratio, 0.5)

    def test_trade_lookup(self):
        e = self.idx.lookup_trade("科技发展")
        self.assertIsNotNone(e)

    def test_addr_lookup(self):
        e = self.idx.lookup_addr("深圳市南山区")
        self.assertIsNotNone(e)

    def test_suffix_not_found(self):
        self.assertIsNone(self.idx.lookup_suffix("zzzzz"))

    def test_trade_exact_not_contains(self):
        self.assertIn("国贸", self.idx.trade)
