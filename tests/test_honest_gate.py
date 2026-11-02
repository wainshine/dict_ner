"""诚实子集门禁回归 — 排除集 / md5 血缘 / verdict"""
import hashlib
import json
import os
import sys
import tempfile
import unittest

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from v3.honest_gate import (file_md5, gate_verdict, honest_mask,
                            manifest_train_texts, resolve_manifest)


class TestHonestMask(unittest.TestCase):
    def test_union_exclusion_and_strip(self):
        df = pd.DataFrame({"text": [" A ", "B", "C", "D"], "label": ["ORG"] * 4})
        mask = honest_mask(df, {"A", "C"})
        self.assertEqual(mask.tolist(), [False, True, False, True])


class TestGateVerdict(unittest.TestCase):
    def test_tolerance(self):
        self.assertEqual(gate_verdict(0.9050, 0.9050, 0.002), "PASS")
        self.assertEqual(gate_verdict(0.9031, 0.9050, 0.002), "PASS")
        self.assertEqual(gate_verdict(0.9029, 0.9050, 0.002), "FAIL")
        self.assertEqual(gate_verdict(0.9100, 0.9050, 0.0), "PASS")


class TestManifestLineage(unittest.TestCase):
    def test_md5_and_train_texts(self):
        with tempfile.TemporaryDirectory() as d:
            train = os.path.join(d, "train.csv")
            pd.DataFrame({"text": ["甲", "乙", "甲"], "label": ["ORG", "POI", "ORG"]}) \
                .to_csv(train, index=False)
            with open(train, "rb") as f:
                md5 = hashlib.md5(f.read()).hexdigest()
            manifest = {"train_path": train, "train_md5": md5}
            texts = manifest_train_texts(manifest, "test")
            self.assertEqual(texts, {"甲", "乙"})
            self.assertEqual(file_md5(train), md5)

            manifest["train_md5"] = "0" * 32
            with self.assertRaises(SystemExit):
                manifest_train_texts(manifest, "test")

    def test_resolve_manifest_archive_naming(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("manifest_v3.json", "manifest_v3_baseline_v42.json",
                         "manifest_exp_x.json"):
                with open(os.path.join(d, name), "w") as f:
                    json.dump({}, f)
            self.assertTrue(resolve_manifest(os.path.join(d, "clf_v3.pkl"))
                            .endswith("manifest_v3.json"))
            self.assertTrue(resolve_manifest(os.path.join(d, "clf_v3_baseline_v42.pkl"))
                            .endswith("manifest_v3_baseline_v42.json"))
            self.assertTrue(resolve_manifest(os.path.join(d, "exp_x.pkl"))
                            .endswith("manifest_exp_x.json"))


if __name__ == "__main__":
    unittest.main()
