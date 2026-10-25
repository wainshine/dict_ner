"""Batch 0 回归测试 — 版本单一来源 / val_pred 路径 / precompute 清理 / 原子写 / 词典 fail-fast"""
import os
import pickle
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import SYSTEM_VERSION
from tools.pipeline_base import atomic_pickle_dump


class TestSystemVersion(unittest.TestCase):
    def test_single_source(self):
        import run
        import serve
        self.assertEqual(run.VERSION, SYSTEM_VERSION)
        self.assertEqual(serve.SYSTEM_VERSION, SYSTEM_VERSION)
        self.assertEqual(serve.app.version, SYSTEM_VERSION)


class TestValPredPath(unittest.TestCase):
    def test_paths(self):
        from v3.train import DEFAULT_MODEL, resolve_val_pred_path
        self.assertTrue(resolve_val_pred_path(DEFAULT_MODEL)
                        .endswith(os.path.join("output", "v3_feat", "val_pred.csv")))
        self.assertIsNone(resolve_val_pred_path("models/experiment.pkl"))
        self.assertEqual(resolve_val_pred_path("models/experiment.pkl", "/tmp/vp.csv"),
                         "/tmp/vp.csv")


class TestAtomicPickle(unittest.TestCase):
    def test_backup_and_no_tmp(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.pkl")
            atomic_pickle_dump({"a": 1}, path)
            atomic_pickle_dump({"a": 2}, path)
            with open(path, "rb") as f:
                self.assertEqual(pickle.load(f), {"a": 2})
            with open(path + ".bak", "rb") as f:
                self.assertEqual(pickle.load(f), {"a": 1})
            self.assertFalse(os.path.exists(path + ".tmp"))


class TestPrecomputeBatch0(unittest.TestCase):
    def test_run_without_chunks_keeps_features(self):
        import v3.precompute as p
        with tempfile.TemporaryDirectory() as d:
            chunks = os.path.join(d, "chunks")
            feats = os.path.join(d, "feats")
            os.makedirs(chunks)
            os.makedirs(feats)
            keep = os.path.join(feats, "keep.txt")
            with open(keep, "w") as f:
                f.write("keep")
            old = (p.CHUNK_DIR, p.FEAT_DIR)
            p.CHUNK_DIR, p.FEAT_DIR = chunks, feats
            try:
                self.assertFalse(p.run())
                self.assertTrue(os.path.exists(keep))
            finally:
                p.CHUNK_DIR, p.FEAT_DIR = old

    def test_merge_only_current_chunks(self):
        import csv
        import v3.precompute as p
        with tempfile.TemporaryDirectory() as d:
            chunks = os.path.join(d, "chunks")
            feats = os.path.join(d, "feats")
            os.makedirs(chunks)
            os.makedirs(feats)
            for name in ("chunk_00.csv", "chunk_01.csv"):
                with open(os.path.join(chunks, name), "w") as f:
                    f.write("text,label\na,ORG\n")
                with open(os.path.join(feats, name), "w") as f:
                    f.write("text,label\na,ORG\n")
            with open(os.path.join(feats, "chunk_09.csv"), "w") as f:
                f.write("text,label\nstale,X\n")
            old = (p.CHUNK_DIR, p.FEAT_DIR)
            p.CHUNK_DIR, p.FEAT_DIR = chunks, feats
            out = os.path.join(d, "out.csv")
            try:
                p.merge(out)
                with open(out) as f:
                    rows = list(csv.reader(f))
                self.assertEqual(len(rows), 3)  # header + 2 current chunks
                with open(out) as f:
                    self.assertNotIn("stale", f.read())
            finally:
                p.CHUNK_DIR, p.FEAT_DIR = old


class TestDictFailFast(unittest.TestCase):
    def test_missing_dict_raises(self):
        from v3.engine.configs import _load_org_dicts
        with self.assertRaises(FileNotFoundError):
            _load_org_dicts("poi___missing__.pkl", "v1.1.2")


if __name__ == "__main__":
    unittest.main()
