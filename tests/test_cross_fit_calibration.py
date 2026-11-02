"""cross-fit isotonic 校准回归 — OOF 拟合 / runtime duck-type / pickle 往返"""
import os
import pickle
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from v3.calibration import (CrossFitCalibrated, _CalibratedView,
                            fit_isotonic_calibrators)
from v3.infer import finalize_proba
from v3.train import assign_group_folds


class TestFinalizeTemperature(unittest.TestCase):
    def test_preserves_argmax_only_changes_confidence(self):
        rng = np.random.RandomState(3)
        proba = rng.dirichlet([1, 1, 1, 1], size=200)
        mult = np.array([0.7, 0.7, 0.55, 1.5])
        pred0, conf0 = finalize_proba(proba, mult, 0.0)
        pred1, conf1 = finalize_proba(proba, mult, 0.0, 1.4)
        np.testing.assert_array_equal(pred0, pred1)
        self.assertFalse(np.allclose(conf0, conf1))
        self.assertTrue(np.all((conf1 >= 0) & (conf1 <= 1)))

    def test_default_temperature_is_identity(self):
        rng = np.random.RandomState(4)
        proba = rng.dirichlet([1, 1, 1, 1], size=50)
        mult = np.array([0.7, 0.7, 0.55, 1.5])
        a = finalize_proba(proba, mult, 0.0)
        b = finalize_proba(proba, mult, 0.0, 1.0)
        np.testing.assert_allclose(a[1], b[1])
        np.testing.assert_array_equal(a[0], b[0])


class TestGroupFolds(unittest.TestCase):
    def test_groups_stay_together(self):
        groups = np.array(["a"] * 3 + ["b"] * 2 + ["c", "d", "e", "f", "g"])
        folds = assign_group_folds(groups, 3, 42)
        self.assertEqual(folds[0], folds[1])
        self.assertEqual(folds[1], folds[2])
        self.assertEqual(folds[3], folds[4])
        self.assertEqual(set(folds.tolist()), {0, 1, 2})
        np.testing.assert_array_equal(folds, assign_group_folds(groups, 3, 42))



class TestCrossFitCalibrated(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sklearn.ensemble import HistGradientBoostingClassifier
        rng = np.random.RandomState(0)
        cls.X = rng.randn(1200, 6)
        cls.y = rng.randint(0, 4, 1200)
        cls.gbdt = HistGradientBoostingClassifier(max_iter=15, random_state=0)
        cls.gbdt.fit(cls.X, cls.y)
        raw = cls.gbdt.decision_function(cls.X)
        cls.cal = CrossFitCalibrated(
            cls.gbdt,
            fit_isotonic_calibrators(raw, cls.y, cls.gbdt.classes_),
            cls.gbdt.classes_)

    def test_proba_contract(self):
        p = self.cal.predict_proba(self.X[:50])
        self.assertEqual(p.shape, (50, 4))
        self.assertTrue(np.all(p >= 0.0) and np.all(p <= 1.0))
        np.testing.assert_allclose(p.sum(axis=1), 1.0, atol=1e-12)

    def test_fast_predict_compatibility(self):
        from v3.fast_predict import FastCalibrated
        p = self.cal.predict_proba(self.X[:100])
        fast = FastCalibrated(self.cal)
        np.testing.assert_allclose(fast.predict_proba(self.X[:100]), p, atol=1e-9)

    def test_duck_typed_view(self):
        cc = self.cal.calibrated_classifiers_[0]
        self.assertIsInstance(cc, _CalibratedView)
        self.assertIs(cc.estimator, self.gbdt)
        self.assertEqual(len(cc.calibrators), 4)

    def test_pickle_roundtrip(self):
        clone = pickle.loads(pickle.dumps(self.cal))
        p1 = self.cal.predict_proba(self.X[:80])
        p2 = clone.predict_proba(self.X[:80])
        np.testing.assert_allclose(p1, p2, atol=1e-12)


if __name__ == "__main__":
    unittest.main()
