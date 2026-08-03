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
    X = df[feat_cols].to_numpy(dtype=np.float32)
    y = df["label"].map(L2I).to_numpy()
    return df, feat_cols, X, y


def crossval_proba(X, y, folds, seed=42):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.model_selection import StratifiedKFold

    proba = np.zeros((len(y), len(LABELS)), dtype=np.float32)
    skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    for i, (tr, te) in enumerate(skf.split(X, y)):
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
    ap.add_argument("--threshold", type=float, default=0.7)
    ap.add_argument("--folds", type=int, default=3)
    ap.add_argument("--out", default=os.path.join(FEAT_DIR, "pool_feats_clean.csv"))
    args = ap.parse_args()

    df, feat_cols, X, y = load_pool(args.pool)
    print(f"pool: {X.shape}", flush=True)

    proba = crossval_proba(X, y, args.folds)
    pred = proba.argmax(1)
    conf = proba.max(1)

    contradict = (pred != y) & (conf >= args.threshold)
    keep = ~contradict
    print(f"\nthreshold={args.threshold}: drop {contradict.sum():,} "
          f"({100*contradict.mean():.1f}%), keep {keep.sum():,}", flush=True)

    stats = {"threshold": args.threshold, "folds": args.folds,
             "total": int(len(y)), "dropped": int(contradict.sum()),
             "by_label": {}, "by_source_type": {}}
    for lb in LABELS:
        i = L2I[lb]
        mask = y == i
        stats["by_label"][lb] = {
            "total": int(mask.sum()),
            "dropped": int((contradict & mask).sum()),
            "drop_rate": round(float((contradict & mask).mean()), 4),
            "pred_dist_when_dropped": dict(Counter(
                LABELS[p] for p in pred[contradict & mask])),
        }
    for (src, typ), grp in df.groupby(["source", "type_orig"]):
        idx = grp.index.to_numpy()
        rate = float(contradict[idx].mean())
        if len(idx) >= 100:
            stats["by_source_type"][f"{src}|{typ}"] = {
                "total": int(len(idx)), "drop_rate": round(rate, 4)}

    df_clean = df.loc[keep].reset_index(drop=True)
    df_clean.to_csv(args.out, index=False)
    print(f"clean pool: {len(df_clean):,} -> {args.out}", flush=True)

    with open(os.path.join(FEAT_DIR, "pool_clean_stats.json"), "w",
              encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    lines = ["# v3 标签清洗噪声报告 (confident learning)", "",
             f"- pool: {len(y):,} | folds: {args.folds} | threshold: {args.threshold}",
             f"- dropped: {int(contradict.sum()):,} ({100*contradict.mean():.1f}%)",
             f"- kept: {int(keep.sum()):,}", "",
             "## 各类别剔除率", "",
             "| 类别 | 总数 | 剔除 | 剔除率 | 被误判为 |",
             "|------|-----:|-----:|-------:|---------|"]
    for lb in LABELS:
        s = stats["by_label"][lb]
        lines.append(f"| {lb} | {s['total']:,} | {s['dropped']:,} | "
                     f"{s['drop_rate']:.1%} | {s['pred_dist_when_dropped']} |")
    lines += ["", "## 映射级噪声率 (source|type, n>=100, 按剔除率降序 top40)", "",
              "| source\\|type | 总数 | 剔除率 |", "|---|-----:|-------:|"]
    st = sorted(stats["by_source_type"].items(), key=lambda kv: -kv[1]["drop_rate"])
    for k, v in st[:40]:
        lines.append(f"| {k} | {v['total']:,} | {v['drop_rate']:.1%} |")
    report = os.path.join(BASE, "output", "v3_noise_report.md")
    with open(report, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"noise report: {report}", flush=True)


if __name__ == "__main__":
    main()
