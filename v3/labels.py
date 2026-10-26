#!/usr/bin/env python3
"""Confident learning 标签清洗 — k-fold CV 交叉预测, 高置信矛盾样本剔除

用法: python v3/labels.py --pool output/v3_feat/pool_feats.csv [--threshold 0.7] [--folds 3]
产出: output/v3_feat/pool_feats_clean.csv + output/v3_noise_report.md + pool_clean_stats.json
"""
import argparse
import json
import os
import sys
import time
from collections import Counter

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LABELS = ("ORG", "POI", "ADDR", "UNKNOWN")
L2I = {lb: i for i, lb in enumerate(LABELS)}
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEAT_DIR = os.path.join(BASE, "output", "v3_feat")
META_COLS = ["text", "label", "source", "type_orig"]


def load_pool(path):
    df = pd.read_csv(path)
    feat_cols = [c for c in df.columns if c not in META_COLS]
    bad = ~df["label"].isin(LABELS)
    if bad.any():
        examples = df.loc[bad, "label"].astype(str).unique()[:5].tolist()
        raise ValueError(f"unknown labels in pool: {examples} (n={int(bad.sum())})")
    X = df[feat_cols].to_numpy(dtype=np.float32)
    y = df["label"].map(L2I).to_numpy()
    texts = df["text"].astype(str).str.strip().to_numpy()
    return df, feat_cols, X, y, texts


def crossval_proba(X, y, folds, texts=None, seed=42):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold

    proba = np.zeros((len(y), len(LABELS)), dtype=np.float32)
    if texts is not None:
        splitter = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed)
        splits = splitter.split(X, y, groups=texts)
    else:
        splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
        splits = splitter.split(X, y)
    for i, (tr, te) in enumerate(splits):
        t0 = time.time()
        clf = HistGradientBoostingClassifier(
            max_iter=120, learning_rate=0.1, max_leaf_nodes=31,
            min_samples_leaf=40, early_stopping=True,
            validation_fraction=0.08, random_state=seed)
        clf.fit(X[tr], y[tr])
        fold_proba = clf.predict_proba(X[te])
        for col, cls in enumerate(clf.classes_):
            proba[te, int(cls)] = fold_proba[:, col]
        acc = (proba[te].argmax(1) == y[te]).mean()
        print(f"fold {i+1}/{folds}: n_iter={clf.n_iter_}, "
              f"heldout acc={acc:.4f}, {time.time()-t0:.0f}s", flush=True)
    return proba


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default=os.path.join(FEAT_DIR, "pool_feats.csv"))
    ap.add_argument("--threshold", type=float, default=0.7,
                    help="统一剔除阈值 (被 --drop-org 等类条件阈值覆盖)")
    ap.add_argument("--drop-org", type=float, default=None)
    ap.add_argument("--drop-poi", type=float, default=None)
    ap.add_argument("--drop-addr", type=float, default=None)
    ap.add_argument("--flip", type=float, default=None,
                    help="翻转阈值: 矛盾且置信>=此值时改标为预测类 (优先于剔除)")
    ap.add_argument("--folds", type=int, default=3)
    ap.add_argument("--out", default=os.path.join(FEAT_DIR, "pool_feats_clean.csv"))
    ap.add_argument("--stats", default=os.path.join(FEAT_DIR, "pool_clean_stats.json"))
    ap.add_argument("--report", default=os.path.join(BASE, "output", "v3_noise_report.md"))
    args = ap.parse_args()

    drop_t = {L2I["ORG"]: args.drop_org if args.drop_org is not None else args.threshold,
              L2I["POI"]: args.drop_poi if args.drop_poi is not None else args.threshold,
              L2I["ADDR"]: args.drop_addr if args.drop_addr is not None else args.threshold,
              L2I["UNKNOWN"]: args.threshold}

    df, feat_cols, X, y, texts = load_pool(args.pool)
    print(f"pool: {X.shape}", flush=True)

    proba = crossval_proba(X, y, args.folds, texts)
    pred = proba.argmax(1)
    conf = proba.max(1)

    flip_mask = np.zeros(len(y), dtype=bool)
    drop_mask = np.zeros(len(y), dtype=bool)
    for cls_i, t in drop_t.items():
        contradict = (pred != y) & (y == cls_i)
        if args.flip is not None:
            fm = contradict & (conf >= args.flip)
            flip_mask |= fm
            drop_mask |= contradict & (conf >= t) & ~fm
        else:
            drop_mask |= contradict & (conf >= t)

    n_flip, n_drop = int(flip_mask.sum()), int(drop_mask.sum())
    print(f"\nthresholds={drop_t}, flip={args.flip}: "
          f"flip {n_flip:,}, drop {n_drop:,} ({100*n_drop/len(y):.1f}%), "
          f"keep {len(y)-n_drop:,}", flush=True)

    stats = {"threshold": drop_t, "flip": args.flip, "folds": args.folds,
             "total": int(len(y)), "flipped": n_flip, "dropped": n_drop,
             "by_label": {}, "by_source_type": {}}
    for lb in LABELS:
        i = L2I[lb]
        mask = y == i
        if mask.sum() == 0:
            continue
        stats["by_label"][lb] = {
            "total": int(mask.sum()),
            "flipped": int((flip_mask & mask).sum()),
            "dropped": int((drop_mask & mask).sum()),
            "drop_rate": round(float((drop_mask & mask).mean()), 4),
            "pred_dist_when_dropped": dict(Counter(
                LABELS[p] for p in pred[drop_mask & mask])),
        }
    for (src, typ), grp in df.groupby(["source", "type_orig"]):
        idx = grp.index.to_numpy()
        if len(idx) >= 100:
            stats["by_source_type"][f"{src}|{typ}"] = {
                "total": int(len(idx)),
                "drop_rate": round(float(drop_mask[idx].mean()), 4)}

    df.loc[flip_mask, "label"] = [LABELS[p] for p in pred[flip_mask]]
    df_clean = df.loc[~drop_mask].reset_index(drop=True)
    df_clean.to_csv(args.out, index=False)
    print(f"clean pool: {len(df_clean):,} -> {args.out}", flush=True)

    with open(args.stats, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    lines = ["# v3 标签清洗噪声报告 (confident learning)", "",
             f"- pool: {len(y):,} | folds: {args.folds} | drop: {drop_t} | flip: {args.flip}",
             f"- flipped: {n_flip:,} | dropped: {n_drop:,} ({100*n_drop/len(y):.1f}%)",
             f"- kept: {len(y)-n_drop:,}", "",
             "## 各类别剔除率", "",
             "| 类别 | 总数 | 翻转 | 剔除 | 剔除率 | 被误判为 |",
             "|------|-----:|-----:|-----:|-------:|---------|"]
    for lb, s in stats["by_label"].items():
        lines.append(f"| {lb} | {s['total']:,} | {s['flipped']:,} | {s['dropped']:,} | "
                     f"{s['drop_rate']:.1%} | {s['pred_dist_when_dropped']} |")
    lines += ["", "## 映射级噪声率 (source|type, n>=100, 按剔除率降序 top40)", "",
              "| source\\|type | 总数 | 剔除率 |", "|---|-----:|-------:|"]
    st = sorted(stats["by_source_type"].items(), key=lambda kv: -kv[1]["drop_rate"])
    for k, v in st[:40]:
        lines.append(f"| {k} | {v['total']:,} | {v['drop_rate']:.1%} |")
    with open(args.report, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"noise report: {args.report}", flush=True)


if __name__ == "__main__":
    main()
