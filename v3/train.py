#!/usr/bin/env python3
"""v3 分类器训练 — GBDT + isotonic校准 + 类别乘数标定 (val macro-F1)

用法: python v3/train.py [--train X] [--val X] [--model X] [--no-calib]
产出: models/clf_v3.pkl + models/manifest_v3.json + output/v3_feat/val_pred.csv
"""
import argparse
import csv
import hashlib
import json
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.eval_classify import compute_metrics, print_metrics

LABELS = ("ORG", "POI", "ADDR", "UNKNOWN")
L2I = {lb: i for i, lb in enumerate(LABELS)}
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEAT_DIR = os.path.join(BASE, "output", "v3_feat")
MODEL_DIR = os.path.join(BASE, "models")


def load_feats(path):
    df = pd.read_csv(path, keep_default_na=True)
    meta_cols = ["text", "label", "source", "type_orig"]
    feat_cols = [c for c in df.columns if c not in meta_cols]
    X = df[feat_cols].to_numpy(dtype=np.float64)
    y = df["label"].map(L2I).to_numpy()
    return X, y, df, feat_cols


def _metrics(proba, y, mult):
    pred = np.argmax(proba * mult, axis=1)
    pairs = [(LABELS[int(e)], LABELS[int(p)]) for e, p in zip(y, pred)]
    return compute_metrics(pairs), pred


def tune_multipliers(proba, y, grid=None, reject_class=None, reject_grid=None):
    n_cls = proba.shape[1]
    if grid is None:
        grid = np.array([0.25, 0.4, 0.55, 0.7, 0.85, 1.0, 1.2, 1.5, 2.0, 3.0, 5.0, 8.0])
    if reject_grid is None:
        reject_grid = np.array([0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7])
    mult = np.ones(n_cls)
    reject_t = 0.0

    def macro_f1(m, rt):
        mx = proba * m
        pred = np.argmax(mx, axis=1)
        if reject_class is not None and rt > 0:
            low = proba.max(axis=1) < rt
            pred = np.where(low, reject_class, pred)
        pairs = [(LABELS[int(e)], LABELS[int(p)]) for e, p in zip(y, pred)]
        return compute_metrics(pairs)["macro_f1"]

    best = macro_f1(mult, reject_t)
    for _ in range(3):
        improved = False
        for c in range(n_cls):
            cur = mult[c]
            for g in grid:
                if g == cur:
                    continue
                mult[c] = g
                f1 = macro_f1(mult, reject_t)
                if f1 > best + 1e-6:
                    best, cur, improved = f1, g, True
            mult[c] = cur
        if reject_class is not None:
            cur_rt = reject_t
            for rt in reject_grid:
                if rt == cur_rt:
                    continue
                f1 = macro_f1(mult, rt)
                if f1 > best + 1e-6:
                    best, cur_rt, improved = f1, float(rt), True
            reject_t = cur_rt
        if not improved:
            break
    return mult, reject_t, best


def file_md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default=os.path.join(FEAT_DIR, "train_feats.csv"))
    ap.add_argument("--calib-set", default=None,
                    help="prefit校准集 (未参与训练, 如 eval_split_train)")
    ap.add_argument("--val", default=os.path.join(FEAT_DIR, "val_feats.csv"))
    ap.add_argument("--model", default=os.path.join(MODEL_DIR, "clf_v3.pkl"))
    ap.add_argument("--manifest", default=os.path.join(MODEL_DIR, "manifest_v3.json"))
    ap.add_argument("--no-calib", action="store_true")
    ap.add_argument("--max-iter", type=int, default=500)
    ap.add_argument("--max-leaf-nodes", type=int, default=63)
    ap.add_argument("--tag", default="v3.0")
    args = ap.parse_args()

    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.calibration import CalibratedClassifierCV

    t0 = time.time()
    X_tr, y_tr, df_tr, feat_cols = load_feats(args.train)
    X_va, y_va, df_va, _ = load_feats(args.val)
    print(f"train {X_tr.shape}, val {X_va.shape}, features {len(feat_cols)}")

    max_iter = args.max_iter
    clf = HistGradientBoostingClassifier(
        max_iter=max_iter, learning_rate=0.08, max_leaf_nodes=args.max_leaf_nodes,
        min_samples_leaf=40, l2_regularization=1.0,
        early_stopping=True, validation_fraction=0.1, random_state=42)
    clf.fit(X_tr, y_tr)
    print(f"GBDT fit done in {time.time()-t0:.0f}s, n_iter={clf.n_iter_}")

    if args.no_calib:
        pass
    elif args.calib_set:
        from sklearn.frozen import FrozenEstimator
        X_ca, y_ca, _, _ = load_feats(args.calib_set)
        keep = np.isin(y_ca, list(clf.classes_))
        X_ca, y_ca = X_ca[keep], y_ca[keep]
        clf = CalibratedClassifierCV(FrozenEstimator(clf), method="isotonic")
        clf.fit(X_ca, y_ca)
        print(f"prefit isotonic calibration on {len(y_ca):,} rows "
              f"({time.time()-t0:.0f}s total)")
    else:
        clf = CalibratedClassifierCV(clf, method="isotonic", cv=3)
        clf.fit(X_tr, y_tr)
        print(f"isotonic calibration done in {time.time()-t0:.0f}s total")

    classes = [int(c) for c in clf.classes_]
    proba_raw = clf.predict_proba(X_va)
    proba = np.zeros((len(y_va), len(LABELS)))
    for col, cls in enumerate(classes):
        proba[:, cls] = proba_raw[:, col]

    has_unknown_model = L2I["UNKNOWN"] in classes
    reject_class = None if has_unknown_model else L2I["UNKNOWN"]

    def predict(mult, rt):
        mx = proba * mult
        pred = np.argmax(mx, axis=1)
        if reject_class is not None and rt > 0:
            pred = np.where(proba.max(axis=1) < rt, reject_class, pred)
        return pred

    def metrics_of(pred):
        pairs = [(LABELS[int(e)], LABELS[int(p)]) for e, p in zip(y_va, pred)]
        return compute_metrics(pairs)

    m_raw = metrics_of(predict(np.ones(len(LABELS)), 0.0))
    print_metrics(m_raw, "=== val: argmax (no tuning) ===")

    mult, reject_t, best_f1 = tune_multipliers(proba, y_va, reject_class=reject_class)
    print(f"\ntuned multipliers: {dict(zip(LABELS, mult.tolist()))}")
    if reject_class is not None:
        print(f"reject threshold (UNKNOWN): {reject_t}")
    pred_tuned = predict(mult, reject_t)
    m_tuned = metrics_of(pred_tuned)
    print_metrics(m_tuned, "=== val: tuned ===")

    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(args.model, "wb") as f:
        pickle.dump({
            "clf": clf,
            "multipliers": mult.tolist(),
            "reject_t": reject_t,
            "labels": LABELS,
            "feature_names": feat_cols,
        }, f)
    print(f"\nSaved model: {args.model}")

    manifest = {
        "tag": args.tag,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "train_path": args.train, "train_md5": file_md5(args.train),
        "val_path": args.val, "val_md5": file_md5(args.val),
        "n_train": int(len(y_tr)), "n_val": int(len(y_va)),
        "n_features": len(feat_cols),
        "params": {
            "max_iter": args.max_iter, "learning_rate": 0.08, "max_leaf_nodes": args.max_leaf_nodes,
            "min_samples_leaf": 40, "l2_regularization": 1.0,
            "calibration": "isotonic" if not args.no_calib else "none",
        },
        "multipliers": dict(zip(LABELS, [float(m) for m in mult])),
        "reject_t": reject_t,
        "val_argmax": {k: v for k, v in m_raw.items() if k != "confusion_matrix"},
        "val_tuned": {k: v for k, v in m_tuned.items() if k != "confusion_matrix"},
    }
    with open(args.manifest, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"Saved manifest: {args.manifest}")

    pred_path = os.path.join(FEAT_DIR, "val_pred.csv")
    with open(pred_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["text", "label", "source", "pred", "confidence"]
                   + [f"p_{lb}" for lb in LABELS])
        mx = proba * mult
        conf = mx.max(axis=1) / mx.sum(axis=1)
        for i in range(len(df_va)):
            w.writerow([df_va.iloc[i]["text"], df_va.iloc[i]["label"],
                        df_va.iloc[i]["source"], LABELS[pred_tuned[i]],
                        round(float(conf[i]), 4)]
                       + [round(float(p), 4) for p in proba[i]])
    print(f"Saved val predictions: {pred_path}")


if __name__ == "__main__":
    main()
