"""v3 推理 — 加载 GBDT 分类器, classify/recognize 对外契约兼容 v2.x"""
import os
import pickle
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import SegType
from v3.features import FeatureExtractor, FEATURE_NAMES

LABELS = ("ORG", "POI", "ADDR", "UNKNOWN")
L2I = {lb: i for i, lb in enumerate(LABELS)}
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_MODEL = os.path.join(BASE, "models", "clf_v3.pkl")

_ORG_TYPE_REMAP = {"POI": "ORG_SUFFIX"}


class V3Classifier:
    def __init__(self, model_path: str = DEFAULT_MODEL):
        with open(model_path, "rb") as f:
            bundle = pickle.load(f)
        self.clf = bundle["clf"]
        self.mult = np.array(bundle["multipliers"])
        self.reject_t = bundle.get("reject_t", 0.0)
        self.labels = bundle["labels"]
        self.feature_names = bundle["feature_names"]
        self.classes_ = [int(c) for c in self.clf.classes_]
        self.extractor = FeatureExtractor()
        self.pipe = self.extractor.pipe

    def _predict(self, text):
        f = self.extractor.extract(text)
        vec = np.array([[f.get(name, np.nan) for name in self.feature_names]],
                       dtype=np.float64)
        raw = self.clf.predict_proba(vec)[0]
        proba = np.zeros(len(LABELS))
        for col, cls in enumerate(self.classes_):
            proba[cls] = raw[col]
        tuned = proba * self.mult
        cat_i = int(np.argmax(tuned))
        if proba.max() < self.reject_t:
            cat_i = L2I["UNKNOWN"]
        confidence = float(tuned[cat_i] / tuned.sum())
        return self.labels[cat_i], confidence, proba, f

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
        category, confidence, proba, _ = self._predict(text)
        loc_res, org_res, poi_res = self.extractor.last_results

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
            f = self.extractor.extract(t)
            vecs.append([f.get(name, np.nan) for name in self.feature_names])
            seg_results.append(self.extractor.last_results)
        idx_valid = [i for i, v in enumerate(vecs) if v is not None]
        probas = np.zeros((len(idx_valid), len(LABELS)))
        if idx_valid:
            X = np.array([vecs[i] for i in idx_valid], dtype=np.float64)
            raw = self.clf.predict_proba(X)
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
            tuned = proba * self.mult
            cat_i = int(np.argmax(tuned))
            if proba.max() < self.reject_t:
                cat_i = L2I["UNKNOWN"]
            category = self.labels[cat_i]
            confidence = float(tuned[cat_i] / tuned.sum())
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
