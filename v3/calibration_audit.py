#!/usr/bin/env python3
"""置信度可靠性审计 — confidence 分桶 vs 实际准确率, ECE + Brier

用法: python v3/calibration_audit.py [--feats output/v3_feat/val_feats.csv]
产出: output/v3_calibration_report.md
"""
import argparse
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LABELS = ("ORG", "POI", "ADDR", "UNKNOWN")
L2I = {lb: i for i, lb in enumerate(LABELS)}
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feats", default=os.path.join(BASE, "output", "v3_feat", "val_feats.csv"))
    ap.add_argument("--model", default=os.path.join(BASE, "models", "clf_v3.pkl"))
    ap.add_argument("--bins", type=int, default=10)
    args = ap.parse_args()

    with open(args.model, "rb") as f:
        bundle = pickle.load(f)
    mult = np.array(bundle["multipliers"])
    reject_t = bundle.get("reject_t", 0.0)
    from v3.fast_predict import FastCalibrated
    fast = FastCalibrated(bundle["clf"])

    df = pd.read_csv(args.feats, low_memory=False)
    X = df[bundle["feature_names"]].to_numpy(dtype=np.float64)
    y = df["label"].to_numpy()
    proba = fast.predict_proba(X)
    tuned = proba * mult
    pred_i = np.argmax(tuned, axis=1)
    conf = tuned.max(axis=1) / tuned.sum(axis=1)
    pred = np.array([LABELS[i] for i in pred_i])
    if reject_t > 0:
        pred = np.where(proba.max(axis=1) < reject_t, "UNKNOWN", pred)
    correct = (pred == y)

    edges = np.linspace(0.0, 1.0, args.bins + 1)
    rows = []
    ece = 0.0
    n = len(y)
    for i in range(args.bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (conf >= lo) & (conf < hi if i < args.bins - 1 else conf <= hi)
        cnt = int(mask.sum())
        if cnt == 0:
            rows.append((f"{lo:.1f}-{hi:.1f}", 0, 0.0, 0.0, 0.0))
            continue
        mc = float(conf[mask].mean())
        acc = float(correct[mask].mean())
        ece += cnt / n * abs(acc - mc)
        rows.append((f"[{lo:.1f},{hi:.1f})", cnt, mc, acc, acc - mc))

    brier = float(np.mean((proba.max(axis=1) - correct.astype(float)) ** 2))
    overall_acc = float(correct.mean())
    overall_conf = float(conf.mean())

    lines = ["# 置信度可靠性审计", "",
             f"- feats: {args.feats}", f"- model: {args.model}",
             f"- n={n:,} | overall acc={overall_acc:.4f} | mean conf={overall_conf:.4f}",
             f"- **ECE = {ece:.4f}** | Brier = {brier:.4f}", "",
             "## 可靠性表", "",
             "| 置信度桶 | 样本数 | 平均置信度 | 实际准确率 | 差值(acc-conf) |",
             "|---------|-------:|-----------:|-----------:|---------------:|"]
    for rng_, cnt, mc, acc, diff in rows:
        lines.append(f"| {rng_} | {cnt:,} | {mc:.3f} | {acc:.3f} | {diff:+.3f} |")

    lines += ["", "## 分类别可靠性 (>0.7 桶)", "",
              "| 类别 | 样本数 | 准确率 | 平均置信度 |", "|------|-------:|-------:|-----------:|"]
    high = conf >= 0.7
    for lb in LABELS:
        m = high & (pred == lb)
        if m.sum() == 0:
            continue
        lines.append(f"| {lb} | {m.sum():,} | {correct[m].mean():.3f} | {conf[m].mean():.3f} |")

    verdict = ("校准合格, confidence 可直接用于概率路由 (高置信直出/低置信兜底)"
               if ece < 0.05 else
               "校准偏差较大, 建议下游仅用 confidence 排序, 不做绝对概率解释")
    lines += ["", f"## 结论\n\nECE={ece:.4f} → {verdict}"]

    out = os.path.join(BASE, "output", "v3_calibration_report.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines[:30]))
    print(f"\nreport: {out}")


if __name__ == "__main__":
    main()
