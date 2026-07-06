"""P3: core/config.py 路径常量 + 配置 单元测试"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config
from core.types import SegType


class TestConfig(unittest.TestCase):

    def test_base_dir_exists(self):
        self.assertTrue(os.path.isdir(config.BASE_DIR))

    def test_data_dir_exists(self):
        self.assertTrue(os.path.isdir(config.DATA_DIR))

    def test_dict_dir_exists(self):
        self.assertTrue(os.path.isdir(config.DICT_DIR))

    def test_version_is_1_1_2(self):
        self.assertEqual(config.VERSION, "v1.1.2")

    def test_num_chunks(self):
        self.assertEqual(config.NUM_CHUNKS, 16)

    def test_addr_types(self):
        self.assertIn(SegType.PROVINCE, config.ADDR_TYPES)
        self.assertIn(SegType.ROAD, config.ADDR_TYPES)
        self.assertNotIn(SegType.POI, config.ADDR_TYPES)
        self.assertNotIn(SegType.BRAND, config.ADDR_TYPES)


if __name__ == "__main__":
    unittest.main()
