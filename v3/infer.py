"""v3 推理 — 加载 GBDT 分类器, classify/recognize 对外契约兼容 v2.x"""
import logging
import os
import pickle
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import SegType
from v3.features import FeatureExtractor, FEATURE_NAMES

logger = logging.getLogger(__name__)

LABELS = ("ORG", "POI", "ADDR", "UNKNOWN")
L2I = {lb: i for i, lb in enumerate(LABELS)}
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODEL = os.path.join(BASE, "models", "clf_v3.pkl")

_ORG_TYPE_REMAP = {"POI": "ORG_SUFFIX"}


def finalize_proba(proba, mult, reject_t):
    """统一 tuned argmax + reject 规则, 返回 (pred_index, confidence)。

    proba: (n, 4) 校准后概率; mult: (4,); reject_t: 低于阈值的样本归 UNKNOWN。
    所有评估/推理路径共用该函数, 避免 clean_eval/calibration_audit 口径分叉。
    """
    tuned = proba * mult
    pred_i = np.argmax(tuned, axis=1)
    if reject_t > 0:
        low = proba.max(axis=1) < reject_t
        pred_i = np.where(low, L2I["UNKNOWN"], pred_i)
    denom = tuned.sum(axis=1)
    denom = np.where(denom == 0, 1.0, denom)
    conf = tuned[np.arange(len(pred_i)), pred_i] / denom
    return pred_i, conf


class V3Classifier:
    def __init__(self, model_path: str = DEFAULT_MODEL):
        with open(model_path, "rb") as f:
            bundle = pickle.load(f)
        self.clf = bundle["clf"]
        self.mult = np.array(bundle["multipliers"])
        self.reject_t = bundle.get("reject_t", 0.0)
        self.labels = bundle["labels"]
        self.feature_names = bundle["feature_names"]
        if list(self.feature_names) != list(FEATURE_NAMES):
            missing = [n for n in FEATURE_NAMES if n not in set(self.feature_names)]
            extra = [n for n in self.feature_names if n not in set(FEATURE_NAMES)]
            first_diff = next(
                (i for i, (a, b) in enumerate(zip(self.feature_names, FEATURE_NAMES))
                 if a != b), None)
            raise ValueError(
                "模型特征与当前 FEATURE_NAMES 不一致, 拒绝加载: "
                f"model={len(self.feature_names)} current={len(FEATURE_NAMES)} "
                f"first_diff={first_diff} missing={missing[:5]} extra={extra[:5]}")
        self.classes_ = [int(c) for c in self.clf.classes_]
        try:
            from v3.fast_predict import FastCalibrated
            self._fast = FastCalibrated(self.clf)
        except Exception as e:
            logger.warning("FastCalibrated unavailable, fallback to sklearn (slow): %s", e)
            self._fast = None
        self.extractor = FeatureExtractor()
        self.pipe = self.extractor.pipe

    def _proba(self, X):
        if self._fast is not None:
            return self._fast.predict_proba(X)
        return self.clf.predict_proba(X)

    def _predict(self, text):
        f, loc_res, org_res, poi_res = self.extractor.extract_with_results(text)
        vec = np.array([[f.get(name, np.nan) for name in self.feature_names]],
                       dtype=np.float64)
        raw = self._proba(vec)[0]
        proba = np.zeros(len(LABELS))
        for col, cls in enumerate(self.classes_):
            proba[cls] = raw[col]
        pred_i, conf = finalize_proba(proba[None, :], self.mult, self.reject_t)
        return (self.labels[int(pred_i[0])], float(conf[0]), proba, f,
                (loc_res, org_res, poi_res))

    def _select_best(self, category, loc_res, org_res, poi_res):
        if category == "ORG":
            d = org_res.to_dict()
            for s in d["segments"]:
                s["type"] = _ORG_TYPE_REMAP.get(s["type"], s["type"])
            return d
        elif category == "POI":
            return poi_res.to_dict() if poi_res else None
        elif category == "ADDR":
            return loc_res.to_dict()
        return None

    def classify(self, text: str) -> dict:
        text = text.strip()
        if not text:
            return {"text": "", "category": "UNKNOWN", "confidence": 1.0,
                    "best": None, "all": None}
        category, confidence, proba, _, results = self._predict(text)
        loc_res, org_res, poi_res = results

        return {
            "text": text,
            "category": category,
            "confidence": round(confidence, 4),
            "proba": {lb: round(float(proba[L2I[lb]]), 4) for lb in LABELS},
            "best": self._select_best(category, loc_res, org_res, poi_res),
            "all": {
                "loc": loc_res.to_dict(),
                "org": org_res.to_dict(),
                "poi": poi_res.to_dict() if poi_res else None,
            },
        }

    def classify_batch(self, texts) -> list:
        texts = [t.strip() for t in texts]
        vecs = []
        seg_results = []
        for t in texts:
            if not t:
                vecs.append(None)
                seg_results.append(None)
                continue
            f, loc_res, org_res, poi_res = self.extractor.extract_with_results(t)
            vecs.append([f.get(name, np.nan) for name in self.feature_names])
            seg_results.append((loc_res, org_res, poi_res))
        idx_valid = [i for i, v in enumerate(vecs) if v is not None]
        probas = np.zeros((len(idx_valid), len(LABELS)))
        if idx_valid:
            X = np.array([vecs[i] for i in idx_valid], dtype=np.float64)
            raw = self._proba(X)
            for col, cls in enumerate(self.classes_):
                probas[:, cls] = raw[:, col]
        out = []
        res_i = 0
        for i, t in enumerate(texts):
            if vecs[i] is None:
                out.append({"text": "", "category": "UNKNOWN", "confidence": 1.0,
                            "best": None, "all": None})
                continue
            proba = probas[res_i]
            res_i += 1
            pred_i, conf = finalize_proba(proba[None, :], self.mult, self.reject_t)
            category = self.labels[int(pred_i[0])]
            confidence = float(conf[0])
            loc_res, org_res, poi_res = seg_results[i]
            out.append({
                "text": t,
                "category": category,
                "confidence": round(confidence, 4),
                "proba": {lb: round(float(proba[L2I[lb]]), 4) for lb in LABELS},
                "best": self._select_best(category, loc_res, org_res, poi_res),
                "all": {
                    "loc": loc_res.to_dict(),
                    "org": org_res.to_dict(),
                    "poi": poi_res.to_dict() if poi_res else None,
                },
            })
        return out
