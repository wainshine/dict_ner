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

from tools.metrics import compute_metrics, print_metrics

LABELS = ("ORG", "POI", "ADDR", "UNKNOWN")
L2I = {lb: i for i, lb in enumerate(LABELS)}
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEAT_DIR = os.path.join(BASE, "output", "v3_feat")
MODEL_DIR = os.path.join(BASE, "models")
DEFAULT_MODEL = os.path.join(MODEL_DIR, "clf_v3.pkl")
DEFAULT_MANIFEST = os.path.join(MODEL_DIR, "manifest_v3.json")


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


def _ece(conf, pred, y, bins=10):
    correct = (pred == y).astype(np.float64)
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (conf > lo) & (conf <= hi) if lo > 0 else (conf >= lo) & (conf <= hi)
        if mask.sum() == 0:
            continue
        total += mask.mean() * abs(correct[mask].mean() - conf[mask].mean())
    return float(total)


def tune_confidence_temperature(proba, y, mult, reject_t):
    """在 val 上拟合 confidence temperature, 只改置信度不改 argmax."""
    from v3.infer import finalize_proba
    best_t, best_ece = 1.0, float("inf")
    for t in np.arange(1.0, 2.001, 0.05):
        pred, conf = finalize_proba(proba, mult, reject_t, float(t))
        e = _ece(conf, pred, y)
        if e < best_ece - 1e-12:
            best_t, best_ece = round(float(t), 2), e
    return best_t, best_ece


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


def resolve_val_pred_path(model_path, explicit=None):
    """返回 val_pred 输出路径; None 表示不写。

    只有基线模型 (clf_v3.pkl) 默认写 output/v3_feat/val_pred.csv;
    实验模型 (--model 指向新文件) 必须显式 --val-pred 才写, 避免覆盖基线产物。
    """
    if explicit:
        return explicit
    if os.path.abspath(model_path) == os.path.abspath(DEFAULT_MODEL):
        return os.path.join(FEAT_DIR, "val_pred.csv")
    return None


def resolve_manifest_path(model_path, explicit=None):
    """返回 manifest 输出路径。

    基线 model 默认写 models/manifest_v3.json;
    实验 model 默认写同目录 manifest_<model_stem>.json, 避免覆盖基线 manifest。
    """
    if explicit:
        return explicit
    if os.path.abspath(model_path) == os.path.abspath(DEFAULT_MODEL):
        return DEFAULT_MANIFEST
    stem = os.path.splitext(os.path.basename(model_path))[0]
    return os.path.join(os.path.dirname(os.path.abspath(model_path)),
                        f"manifest_{stem}.json")


def make_gbdt(args, random_state):
    from sklearn.ensemble import HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(
        max_iter=args.max_iter, learning_rate=0.08, max_leaf_nodes=args.max_leaf_nodes,
        min_samples_leaf=40, l2_regularization=1.0,
        early_stopping=True, validation_fraction=0.1, random_state=random_state)


def assign_group_folds(groups, k, seed):
    """把整组文本随机分到 k 折 (group 不跨折).

    不用 StratifiedGroupKFold: 260 万 group 时其 Python 逐组循环要 >10min.
    组数远大于 k 时随机分组已足够均衡 (类分布偏差 <0.001), 校准只关心
    OOF 预测的覆盖, 不要求每折严格同分布.
    """
    codes, _ = pd.factorize(groups)
    n_groups = int(codes.max()) + 1
    fold_of_group = np.empty(n_groups, dtype=np.int8)
    fold_of_group[np.random.RandomState(seed).permutation(n_groups)] = (
        np.arange(n_groups) % k)
    return fold_of_group[codes]


def cross_fit_fit(args, X_tr, y_tr, df_tr, X_ca, y_ca, df_ca):
    """K-fold OOF isotonic 校准 + 全量 GBDT.

    训练行 = train + calib (calib 不再 held-out); 每个 fold 模型对 holdout 折
    输出 decision_function, 汇总 OOF 后拟合逐类 isotonic; 最终模型在全部行上重训.
    返回 (CrossFitCalibrated, n_train)。
    """
    from v3.calibration import CrossFitCalibrated, fit_isotonic_calibrators

    if args.cross_fit < 2:
        raise SystemExit("--cross-fit must be >= 2")
    X = np.vstack([X_tr, X_ca])
    y = np.concatenate([y_tr, y_ca])
    groups = np.concatenate([
        df_tr["text"].astype(str).str.strip().to_numpy(),
        df_ca["text"].astype(str).str.strip().to_numpy(),
    ])
    classes = np.unique(y)
    oof = np.zeros((len(y), len(classes)), dtype=np.float64)
    print(f"  assigning {len(groups):,} rows / text groups to "
          f"{args.cross_fit} folds...", flush=True)
    fold_ids = assign_group_folds(groups, args.cross_fit, args.random_state)
    for fold in range(args.cross_fit):
        tr_idx = np.flatnonzero(fold_ids != fold)
        va_idx = np.flatnonzero(fold_ids == fold)
        tf = time.time()
        fold_clf = make_gbdt(args, args.random_state + fold)
        fold_clf.fit(X[tr_idx], y[tr_idx])
        raw = np.asarray(fold_clf.decision_function(X[va_idx]))
        if raw.ndim == 1:
            raw = raw[:, None]
        if raw.shape[1] != len(classes):
            raise SystemExit(f"OOF class width {raw.shape[1]} != {len(classes)}")
        oof[va_idx] = raw
        print(f"  cross-fit fold {fold + 1}/{args.cross_fit}: "
              f"fit={len(tr_idx):,} oof={len(va_idx):,} n_iter={fold_clf.n_iter_} "
              f"({time.time() - tf:.0f}s)", flush=True)

    calibrators = fit_isotonic_calibrators(oof, y, classes)
    print(f"  OOF isotonic fitted on {len(y):,} rows", flush=True)
    full_clf = make_gbdt(args, args.random_state)
    full_clf.fit(X, y)
    print(f"  full-data fit {len(y):,} rows, n_iter={full_clf.n_iter_}", flush=True)
    return CrossFitCalibrated(full_clf, calibrators, full_clf.classes_), len(y)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default=os.path.join(FEAT_DIR, "final_train7.csv"))
    ap.add_argument("--calib-set", default=os.path.join(FEAT_DIR, "calib_feats.csv"),
                    help="held-out 校准集 (与 train 文本隔离); --no-calib 时忽略")
    ap.add_argument("--val", default=os.path.join(FEAT_DIR, "val_feats.csv"))
    ap.add_argument("--model", default=os.path.join(MODEL_DIR, "clf_v3.pkl"))
    ap.add_argument("--manifest", default=None,
                    help="manifest 输出路径; 默认基线 model → models/manifest_v3.json, "
                         "实验 model → 同目录 manifest_<stem>.json (防覆盖基线)")
    ap.add_argument("--val-pred", default=None,
                    help="val_pred.csv 输出路径; 默认仅当 --model 为基线 clf_v3.pkl 时写 "
                         "output/v3_feat/val_pred.csv, 实验模型默认不写 (防覆盖基线)")
    ap.add_argument("--no-calib", action="store_true")
    ap.add_argument("--cross-fit", type=int, default=0, metavar="K",
                    help="cross-fit isotonic 校准: 把 --calib-set 并入训练, 用 K-fold "
                         "OOF 预测拟合 isotonic (校准诚实且不丢训练行); 0=关闭")
    ap.add_argument("--max-iter", type=int, default=500)
    ap.add_argument("--max-leaf-nodes", type=int, default=63)
    ap.add_argument("--random-state", type=int, default=42,
                    help="GBDT random_state (early-stopping 内部验证集划分)")
    ap.add_argument("--tag", default="v3.0")
    args = ap.parse_args()
    if args.cross_fit and args.no_calib:
        raise SystemExit("--cross-fit and --no-calib are mutually exclusive")
    if args.cross_fit and not args.calib_set:
        raise SystemExit("--cross-fit requires --calib-set (it becomes extra train rows)")

    from sklearn.calibration import CalibratedClassifierCV

    t0 = time.time()
    X_tr, y_tr, df_tr, feat_cols = load_feats(args.train)
    X_va, y_va, df_va, _ = load_feats(args.val)
    print(f"train {X_tr.shape}, val {X_va.shape}, features {len(feat_cols)}")

    if args.cross_fit:
        X_ca, y_ca, df_ca, _ = load_feats(args.calib_set)
        print(f"cross-fit: train + calib = {len(y_tr) + len(y_ca):,} rows, "
              f"K={args.cross_fit}")
        clf, n_train = cross_fit_fit(args, X_tr, y_tr, df_tr, X_ca, y_ca, df_ca)
        print(f"cross-fit calibration done in {time.time() - t0:.0f}s total")
    else:
        clf = make_gbdt(args, args.random_state)
        clf.fit(X_tr, y_tr)
        n_train = len(y_tr)
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

    temperature = 1.0
    val_ece = None
    if args.cross_fit:
        temperature, val_ece = tune_confidence_temperature(
            proba, y_va, mult, reject_t)
        print(f"confidence temperature: {temperature:.2f} "
              f"(val ECE {val_ece:.4f}; 只改 confidence, 不改 argmax)")

    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(args.model, "wb") as f:
        pickle.dump({
            "clf": clf,
            "multipliers": mult.tolist(),
            "reject_t": reject_t,
            "confidence_temperature": temperature,
            "labels": LABELS,
            "feature_names": feat_cols,
        }, f)
    print(f"\nSaved model: {args.model}")

    pred_path = resolve_val_pred_path(args.model, args.val_pred)
    manifest_path = resolve_manifest_path(args.model, args.manifest)
    calib_path = None if args.no_calib else args.calib_set
    calib_mode = ("isotonic_cross_fit" if args.cross_fit
                  else ("none" if args.no_calib else "isotonic"))

    manifest = {
        "tag": args.tag,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "train_path": args.train, "train_md5": file_md5(args.train),
        "val_path": args.val, "val_md5": file_md5(args.val),
        "calib_path": calib_path,
        "calib_md5": file_md5(calib_path) if calib_path else None,
        "train_extra_path": args.calib_set if args.cross_fit else None,
        "train_extra_md5": file_md5(args.calib_set) if args.cross_fit else None,
        "val_pred_path": pred_path,
        "n_train": int(n_train), "n_val": int(len(y_va)),
        "n_features": len(feat_cols),
        "params": {
            "max_iter": args.max_iter, "learning_rate": 0.08, "max_leaf_nodes": args.max_leaf_nodes,
            "min_samples_leaf": 40, "l2_regularization": 1.0,
            "random_state": args.random_state,
            "calibration": calib_mode,
            "cross_fit_folds": args.cross_fit or None,
        },
        "cross_fit": ({"k": args.cross_fit, "group": "text",
                       "seed": args.random_state,
                       "n_oof": int(n_train)} if args.cross_fit else None),
        "multipliers": dict(zip(LABELS, [float(m) for m in mult])),
        "reject_t": reject_t,
        "confidence_temperature": temperature,
        "val_ece": round(val_ece, 4) if val_ece is not None else None,
        "val_argmax": {k: v for k, v in m_raw.items() if k != "confusion_matrix"},
        "val_tuned": {k: v for k, v in m_tuned.items() if k != "confusion_matrix"},
    }
    os.makedirs(os.path.dirname(manifest_path) or ".", exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"Saved manifest: {manifest_path}")

    if pred_path:
        from v3.infer import finalize_proba
        _, conf = finalize_proba(proba, mult, reject_t, temperature)
        with open(pred_path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["text", "label", "source", "pred", "confidence"]
                       + [f"p_{lb}" for lb in LABELS])
            for i in range(len(df_va)):
                w.writerow([df_va.iloc[i]["text"], df_va.iloc[i]["label"],
                            df_va.iloc[i]["source"], LABELS[pred_tuned[i]],
                            round(float(conf[i]), 4)]
                           + [round(float(p), 4) for p in proba[i]])
        print(f"Saved val predictions: {pred_path}")
    else:
        print("Skipped val_pred.csv (non-default model; pass --val-pred to write explicitly)")


if __name__ == "__main__":
    main()
