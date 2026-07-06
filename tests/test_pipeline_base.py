"""P1: tools/pipeline_base.py 共享函数 单元测试"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.pipeline_base import (
    count_lines, split_file, aggregate_stats_files, export_d2_csv,
    clean_stats,
)
from collections import Counter


class TestCountLines(unittest.TestCase):

    def test_count_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("line1\nline2\nline3\n")
            tmp = f.name
        try:
            self.assertEqual(count_lines(tmp), 3)
        finally:
            os.unlink(tmp)

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            tmp = f.name
        try:
            self.assertEqual(count_lines(tmp), 0)
        finally:
            os.unlink(tmp)

    def test_missing_file(self):
        self.assertEqual(count_lines("/nonexistent/path.csv"), 0)


class TestSplitFile(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.source = os.path.join(self.tmpdir, "source.csv")
        with open(self.source, "w", encoding="utf-8") as f:
            for i in range(100):
                f.write(f"line_{i}\n")

    def test_split_into_chunks(self):
        dest = os.path.join(self.tmpdir, "chunks")
        total = split_file(self.source, dest, num_chunks=4)
        self.assertEqual(total, 100)

        chunk_files = sorted([
            f for f in os.listdir(dest) if f.startswith("chunk_")
        ])
        self.assertEqual(len(chunk_files), 4)

        # Count total lines across chunks
        total_lines = 0
        for cf in chunk_files:
            with open(os.path.join(dest, cf), encoding="utf-8") as f:
                total_lines += sum(1 for _ in f)
        self.assertEqual(total_lines, 100)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestCleanStats(unittest.TestCase):

    def test_clean_stats(self):
        tmpdir = tempfile.mkdtemp()
        os.makedirs(tmpdir, exist_ok=True)
        pf = os.path.join(tmpdir, "org_stats_test.pkl")
        with open(pf, "w") as f:
            f.write("dummy")
        clean_stats(tmpdir, "org_stats_")
        self.assertFalse(os.path.exists(pf))
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


class TestAggregateStatsFiles(unittest.TestCase):

    def test_aggregate_basic(self):
        import pickle
        tmpdir = tempfile.mkdtemp()
        files = []
        for i in range(3):
            stats = {
                "total": 10, "d2_hit": 5, "d3_hit": 3, "d4_hit": 2,
                "d1_freqs": Counter({"北京": 10 + i}),
                "d2_freqs": Counter({"华为": 5}),
                "d3_freqs": Counter({"技术": 3}),
                "d4_freqs": Counter({"有限公司": 2}),
                "d4_cats": Counter({"商业": 2}),
                "seg_dist": Counter({3: 5, 4: 5}),
            }
            pf = os.path.join(tmpdir, f"stats_{i:02d}.pkl")
            with open(pf, "wb") as f:
                pickle.dump(stats, f)
            files.append(pf)

        merged = aggregate_stats_files(files)
        self.assertEqual(merged["total"], 30)
        self.assertEqual(merged["d2_hit"], 15)
        self.assertEqual(merged["d1_freqs"]["北京"], 33)  # 10+11+12
        self.assertEqual(merged["d4_cats"]["商业"], 6)

        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_missing_file_skipped(self):
        import pickle
        tmpdir = tempfile.mkdtemp()
        stats = {"total": 5, "d2_hit": 1, "d3_hit": 1, "d4_hit": 1,
                 "d1_freqs": Counter(), "d2_freqs": Counter(),
                 "d3_freqs": Counter(), "d4_freqs": Counter(),
                 "d4_cats": Counter(), "seg_dist": Counter()}
        pf = os.path.join(tmpdir, "stats_00.pkl")
        with open(pf, "wb") as f:
            pickle.dump(stats, f)

        merged = aggregate_stats_files([pf, "/nonexistent/stats_01.pkl"])
        self.assertEqual(merged["total"], 5)

        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


class TestExportD2Csv(unittest.TestCase):

    def test_export(self):
        import csv
        tmpdir = tempfile.mkdtemp()
        out_path = os.path.join(tmpdir, "d2_test.csv")
        d2 = Counter({"中国": 100, "华为": 50, "字节跳动": 30})
        export_d2_csv(d2, out_path)

        self.assertTrue(os.path.exists(out_path))
        with open(out_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["d2_text"], "中国")
        self.assertEqual(rows[0]["freq"], "100")

        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
