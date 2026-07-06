"""P1: loc/builder.py chunk loading 单元测试"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import SegType
from loc.builder import DictBuilder


class TestDictBuilderBuildFromChunks(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.cachedir = os.path.join(cls.tmpdir, "cache")
        os.makedirs(cls.cachedir)

        # Create fake split/loc chunks
        cls.splitdir = os.path.join(cls.tmpdir, "split", "loc")
        os.makedirs(cls.splitdir)

        lines = [
            "上海市浦东新区陆家嘴,100\n",
            "北京市朝阳区望京,50\n",
            "深圳市南山区科技园,30\n",
        ]
        for i in range(4):
            chunk_path = os.path.join(cls.splitdir, f"chunk_{i:02d}.csv")
            with open(chunk_path, "w", encoding="utf-8") as f:
                f.write("dict,idf\n")
                for line in lines:
                    f.write(line)

    def test_scan_loc36kw_chunks(self):
        import glob
        chunk_files = sorted(glob.glob(os.path.join(self.splitdir, "chunk_*.csv")))
        builder = DictBuilder(self.cachedir, "test_chunks")
        counters = builder._scan_loc36kw_chunks(chunk_files)

        self.assertIn(SegType.CITY, counters)
        self.assertIn(SegType.DISTRICT, counters)

        # "上海市" should be in CITY counter
        city_words = dict(counters[SegType.CITY])
        self.assertIn("上海市", city_words)
        self.assertGreater(city_words["上海市"], 0)

    def test_empty_chunk(self):
        empty_dir = os.path.join(self.tmpdir, "empty_split")
        os.makedirs(empty_dir, exist_ok=True)
        builder = DictBuilder(self.cachedir, "test_empty")
        counters = builder._scan_loc36kw_chunks([])
        self.assertEqual(len(counters), 0)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
