"""v3/fast_predict.py 单元测试 — FastCalibrated 与 sklearn 零误差"""
import os
import pickle
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE, "models", "clf_v3.pkl")
FEATS_PATH = os.path.join(BASE, "output", "v3_feat", "test_feats.csv")


@unittest.skipUnless(os.path.exists(MODEL_PATH), "v3 model not found")
class TestFastPredict(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(MODEL_PATH, "rb") as f:
            bundle = pickle.load(f)
        cls.clf = bundle["clf"]
        cls.names = bundle["feature_names"]
        from v3.fast_predict import FastCalibrated
        cls.fast = FastCalibrated(cls.clf)

    def _sample_matrix(self, n=50):
        if not os.path.exists(FEATS_PATH):
            raise unittest.SkipTest("test_feats.csv not found")
        import csv
        rows = []
        with open(FEATS_PATH, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows.append([float(row[c]) if row[c] not in ("", "nan") else np.nan
                             for c in self.names])
                if len(rows) >= n:
                    break
        return np.array(rows, dtype=np.float64)

    def test_proba_zero_diff(self):
        X = self._sample_matrix(50)
        ref = self.clf.predict_proba(X)
        fast = self.fast.predict_proba(X)
        self.assertEqual(ref.shape, fast.shape)
        np.testing.assert_allclose(fast, ref, atol=1e-9, rtol=0)

    def test_proba_sums_to_one(self):
        X = self._sample_matrix(20)
        fast = self.fast.predict_proba(X)
        np.testing.assert_allclose(fast.sum(axis=1), 1.0, atol=1e-6)

    def test_single_row_matches_batch(self):
        # 叶掩码回归: 单行的提前到叶不应影响批内其他行
        X = self._sample_matrix(10)
        batch = self.fast.predict_proba(X)
        for i in range(len(X)):
            single = self.fast.predict_proba(X[i:i + 1])
            np.testing.assert_allclose(single[0], batch[i], atol=1e-9)


if __name__ == "__main__":
    unittest.main()
