#!/usr/bin/env python3
"""v3 评测 + 错误仪表盘 — 对特征集跑模型, 输出指标和每混淆格错误样例

用法: python v3/evaluate.py --feats X.csv [--model models/clf_v3.pkl] [--report out.md]
"""
import argparse
import os
import pickle
import sys
from collections import Counter

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.metrics import compute_metrics, print_metrics
from v3.infer import finalize_proba

LABELS = ("ORG", "POI", "ADDR", "UNKNOWN")
L2I = {lb: i for i, lb in enumerate(LABELS)}
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
META_COLS = ["text", "label", "source", "type_orig"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feats", required=True)
    ap.add_argument("--model", default=os.path.join(BASE, "models", "clf_v3.pkl"))
    ap.add_argument("--report", default=None)
    ap.add_argument("--topk", type=int, default=50)
    args = ap.parse_args()

    with open(args.model, "rb") as f:
        bundle = pickle.load(f)
    clf, mult = bundle["clf"], np.array(bundle["multipliers"])
    reject_t = bundle.get("reject_t", 0.0)
    feat_cols = bundle["feature_names"]

    df = pd.read_csv(args.feats)
    X = df[feat_cols].to_numpy(dtype=np.float64)
    y = df["label"].to_numpy()
    raw = clf.predict_proba(X)
    proba = np.zeros((len(y), len(LABELS)))
    for col, cls in enumerate([int(c) for c in clf.classes_]):
        proba[:, cls] = raw[:, col]
    pred_i, conf = finalize_proba(proba, mult, reject_t)
    pred = np.array([LABELS[int(i)] for i in pred_i])

    pairs = list(zip(y.tolist(), pred.tolist()))
    metrics = compute_metrics(pairs)
    print_metrics(metrics, f"=== {os.path.basename(args.feats)} ===")

    if args.report:
        lines = ["# v3 错误仪表盘", "",
                 f"- feats: {args.feats}", f"- model: {args.model}",
                 f"- macro-F1: {metrics['macro_f1']:.4f} | accuracy: {metrics['accuracy']:.4f}",
                 "", "## per-class", "",
                 "| 类 | P | R | F1 | support |", "|---|---|---|---|---|"]
        for lb in LABELS:
            p = metrics["per_class"][lb]
            lines.append(f"| {lb} | {p['precision']:.4f} | {p['recall']:.4f} "
                         f"| {p['f1']:.4f} | {p['support']:,} |")
        lines += ["", "## 混淆矩阵", "", "| exp\\pred | " + " | ".join(LABELS) + " |",
                  "|---|---|---|---|---|"]
        for e in LABELS:
            row = metrics["confusion_matrix"][e]
            lines.append(f"| {e} | " + " | ".join(f"{row[p]:,}" for p in LABELS) + " |")

        lines += ["", "## 分 source 指标", "",
                  "| source | n | accuracy | macro-F1 |", "|---|---|---|---|"]
        for src, grp in df.groupby("source"):
            idx = grp.index.to_numpy()
            sp = [(y[i], pred[i]) for i in idx]
            m = compute_metrics(sp)
            lines.append(f"| {src} | {len(idx):,} | {m['accuracy']:.4f} | {m['macro_f1']:.4f} |")

        df_err = df.assign(y=y, pred=pred, conf=conf)
        lines += ["", "## 错误样例 (每混淆格 top, 按置信度降序)", ""]
        for e in LABELS:
            for p in LABELS:
                if e == p:
                    continue
                cell = df_err[(df_err.y == e) & (df_err.pred == p)]
                n = len(cell)
                if n == 0:
                    continue
                lines.append(f"### {e} → {p} ({n:,} 条)")
                lines.append("")
                for _, r in cell.nlargest(args.topk, "conf").iterrows():
                    lines.append(f"- `{r['text']}` (conf={r['conf']:.2f}, "
                                 f"{r['source']}|{r.get('type_orig','')})")
                lines.append("")
        with open(args.report, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"\nreport: {args.report}")


if __name__ == "__main__":
    main()
