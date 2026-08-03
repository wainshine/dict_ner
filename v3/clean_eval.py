#!/usr/bin/env python3
"""clean 评测子集 — 用模型无关的查表信号确认标签, 产出双指标

clean 规则 (特征列直接可得, 不依赖任何模型):
  ORG:  has_comp/has_gov==1 或 d4_cat_ORG==1
  POI:  d4_cat_POI_FAC/POI_STORE==1 或 d4_in_sql==0 或 poi_d4_cat_POI_*==1
  ADDR: loc_geo_cov >= 0.95
  UNKNOWN: all_chinese==0 或 n_digit>=len
子集 = 查表推导类 == 原始标签 的样本 (标签被独立信号确认)

用法: python v3/clean_eval.py [--feats val] [--model models/clf_v3.pkl]
"""
import argparse
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.eval_classify import compute_metrics, print_metrics

LABELS = ("ORG", "POI", "ADDR", "UNKNOWN")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEAT_DIR = os.path.join(BASE, "output", "v3_feat")


def derive_clean_label(df):
    n = len(df)
    derived = np.array([None] * n, dtype=object)
    geo = df["loc_geo_cov"].to_numpy()
    derived[geo >= 0.95] = "ADDR"
    is_org = (df["has_comp"].to_numpy() == 1) | (df["has_gov"].to_numpy() == 1) \
        | (df["d4_cat_ORG"].to_numpy() == 1)
    derived[is_org] = "ORG"
    is_poi = (df["d4_cat_POI_FAC"].to_numpy() == 1) \
        | (df["d4_cat_POI_STORE"].to_numpy() == 1) \
        | (df["d4_in_sql"].to_numpy() == 0) \
        | (df["poi_d4_cat_POI_FAC"].to_numpy() == 1) \
        | (df["poi_d4_cat_POI_STORE"].to_numpy() == 1)
    derived[is_poi & ~is_org] = "POI"
    is_unk = (df["all_chinese"].to_numpy() == 0) \
        | (df["n_digit"].to_numpy() >= df["len"].to_numpy())
    derived[is_unk] = "UNKNOWN"
    return derived


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--feats", default="val", choices=["val", "test"])
    ap.add_argument("--model", default=os.path.join(BASE, "models", "clf_v3.pkl"))
    args = ap.parse_args()

    path = os.path.join(FEAT_DIR, f"{args.feats}_feats.csv")
    df = pd.read_csv(path, low_memory=False)
    with open(args.model, "rb") as f:
        bundle = pickle.load(f)
    clf = bundle["clf"]
    mult = np.array(bundle["multipliers"])
    feat_cols = bundle["feature_names"]

    X = df[feat_cols].to_numpy(dtype=np.float64)
    raw = clf.predict_proba(X)
    proba = np.zeros((len(df), len(LABELS)))
    for col, cls in enumerate([int(c) for c in clf.classes_]):
        proba[:, cls] = raw[:, col]
    pred = np.array([LABELS[i] for i in np.argmax(proba * mult, axis=1)])
    y = df["label"].to_numpy()

    derived = derive_clean_label(df)
    clean_mask = np.array([d == t for d, t in zip(derived, y)])
    print(f"{args.feats}: {len(df):,} total, clean subset {clean_mask.sum():,} "
          f"({100*clean_mask.mean():.1f}%)")

    m_raw = compute_metrics(list(zip(y.tolist(), pred.tolist())))
    print_metrics(m_raw, f"=== {args.feats} 原始标签 (n={len(df):,}) ===")
    m_clean = compute_metrics(list(zip(y[clean_mask].tolist(),
                                       pred[clean_mask].tolist())))
    print_metrics(m_clean, f"=== {args.feats} clean标签 (n={clean_mask.sum():,}) ===")

    disagree = ~clean_mask
    n_dis = int(disagree.sum())
    print(f"\n标签未被查表确认的 {n_dis:,} 条中, 模型与标签一致率: "
          f"{(pred[disagree] == y[disagree]).mean():.2%}")


if __name__ == "__main__":
    main()
