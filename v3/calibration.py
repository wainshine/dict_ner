"""Cross-fit isotonic 校准 — 全部训练行参与 fit, 校准用 out-of-fold 预测.

背景 (v4.2.1): v4.2.0 用 held-out `calib_feats` (23,609 行) 做 isotonic, 校准诚实
但把 2.3 万行从训练中剥离; 诚实子集对比显示 UNKNOWN 类因此回退. cross-fit 把
`calib` 行并入训练, 用 K-fold 的 out-of-fold decision_function 拟合 isotonic:
每个校准点都来自"没见过该行"的模型, 校准仍然诚实, 训练行不丢.

推理仍是单个 GBDT (不是 K 模型 ensemble), 延迟不变. 本类 duck-type
`CalibratedClassifierCV` 中 `v3/fast_predict.py`/`v3/infer.py` 实际用到的接口:
`classes_` / `calibrated_classifiers_[0].estimator` / `.calibrators` / `predict_proba`.
"""
import numpy as np
from sklearn.isotonic import IsotonicRegression


class _CalibratedView:
    """FastCalibrated 需要的单 fold 视图 (estimator + 每类 isotonic)."""

    def __init__(self, estimator, calibrators):
        self.estimator = estimator
        self.calibrators = list(calibrators)


class CrossFitCalibrated:
    """单 GBDT + 在 OOF decision_function 上拟合的逐类 isotonic 校准器."""

    def __init__(self, estimator, calibrators, classes):
        self.estimator = estimator
        self.calibrators = list(calibrators)
        self.classes_ = np.asarray(classes, dtype=int)
        self.calibrated_classifiers_ = [
            _CalibratedView(estimator, self.calibrators)
        ]

    def decision_function(self, X):
        return self.estimator.decision_function(X)

    def predict_proba(self, X):
        raw = np.asarray(self.estimator.decision_function(X), dtype=np.float64)
        if raw.ndim == 1:  # 二分类: 单列 logit → calibrator[0] 为正类
            p1 = np.clip(self.calibrators[0].predict(raw), 0.0, 1.0)
            return np.column_stack([1.0 - p1, p1])
        proba = np.empty_like(raw)
        for c in range(raw.shape[1]):
            proba[:, c] = self.calibrators[c].predict(raw[:, c])
        np.clip(proba, 0.0, 1.0, out=proba)
        denom = proba.sum(axis=1, keepdims=True)
        denom[denom == 0] = 1.0
        return proba / denom


def fit_isotonic_calibrators(oof_scores, y, classes):
    """在 OOF decision score 上按 one-vs-rest 拟合逐类 isotonic.

    oof_scores: (n, n_classes), 列顺序与 classes 一致.
    """
    calibrators = []
    for col, cls in enumerate(classes):
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(oof_scores[:, col], (y == cls).astype(np.float64))
        calibrators.append(iso)
    return calibrators
