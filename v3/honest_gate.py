#!/usr/bin/env python3
"""诚实子集门禁 — 切分/训练集变更时的同口径模型对比.

背景 (v4.2.1): v4.2.0 把评测切分从随机改为文本分组后, headline macro-F1
0.9092→0.9035. 但直接比较新旧模型会被"旧模型训练时见过 val/test 文本"污染.
本工具在 **双方训练集都没见过的文本** 上对比, 并把模型质量与操作点分离:
  - own:    各自训练时标定的 multipliers (部署口径, 默认门禁指标)
  - shared: 两个模型都用 baseline 的 multipliers (隔离模型本身; 不同校准
            方法的分数尺度不同, 跨方法时仅作诊断)
  - argmax: 不乘 multipliers (最接近原始概率)

默认从 manifest 读取 train_path/train_extra_path 构造排除集, 并校验 md5.
用法:
  python3 v3/honest_gate.py \
    --candidate models/clf_v3.pkl --baseline models/clf_v3_baseline_v420.pkl

退出码: 0=PASS, 1=FAIL. 默认要求候选在 val/test 的 own macro-F1
不低于 baseline - tol (默认 0.002). 单 seed 噪声可达 ±0.004, 判 FAIL 前
应至少跑 2-3 个 random_state 的候选 (见 HANDOVER 踩坑 #40).
"""
import argparse
import hashlib
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from tools.metrics import compute_metrics  # noqa: E402
from v3.infer import finalize_proba  # noqa: E402

LABELS = ("ORG", "POI", "ADDR", "UNKNOWN")
L2I = {lb: i for i, lb in enumerate(LABELS)}
FEAT_DIR = os.path.join(BASE, "output", "v3_feat")


def file_md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def resolve_manifest(model_path, explicit=None):
    if explicit:
        return explicit
    stem = os.path.splitext(os.path.basename(model_path))[0]
    d = os.path.dirname(os.path.abspath(model_path))
    # 归档模型用 manifest_v3_baseline_v42.json, 实验模型用 manifest_<stem>.json
    candidates = [os.path.join(d, f"manifest_{stem}.json")]
    if stem == "clf_v3":
        candidates.insert(0, os.path.join(d, "manifest_v3.json"))
    elif stem.startswith("clf_v3_"):
        candidates.append(os.path.join(d, f"manifest_v3_{stem[len('clf_v3_'):]}.json"))
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]


def resolve_path(path):
    if not path:
        return None
    return path if os.path.isabs(path) else os.path.join(BASE, path)


def load_manifest(model_path, explicit=None):
    mpath = resolve_manifest(model_path, explicit)
    if not os.path.exists(mpath):
        raise SystemExit(f"manifest 不存在: {mpath} (可用 --*-manifest 指定)")
    with open(mpath, encoding="utf-8") as f:
        return mpath, json.load(f)


def manifest_train_texts(manifest, label):
    """读取 manifest 声明的训练文本集合, 校验文件与 md5."""
    paths = []
    for key, md5_key in (("train_path", "train_md5"),
                         ("train_extra_path", "train_extra_md5")):
        p = resolve_path(manifest.get(key))
        if not p:
            continue
        if not os.path.exists(p):
            raise SystemExit(f"{label} manifest {key} 不存在: {p}")
        want = manifest.get(md5_key)
        if want:
            got = file_md5(p)
            if got != want:
                raise SystemExit(f"{label} {key} md5 不匹配: {p}\n"
                                 f"  manifest={want}\n  actual  ={got}")
        paths.append(p)
    if not paths:
        raise SystemExit(f"{label} manifest 没有 train_path, 无法构造诚实子集")
    texts = set()
    for p in paths:
        texts |= set(pd.read_csv(p, usecols=["text"], dtype=str)["text"]
                     .str.strip().tolist())
        print(f"  {label} train: {p} -> {len(texts):,} unique texts")
    return texts


def load_bundle(path):
    with open(path, "rb") as f:
        bundle = pickle.load(f)
    for key in ("clf", "multipliers", "feature_names"):
        if key not in bundle:
            raise SystemExit(f"模型缺少字段 {key}: {path}")
    return bundle


def predict_proba(bundle, df):
    clf = bundle["clf"]
    X = df[bundle["feature_names"]].to_numpy(dtype=np.float64)
    raw = clf.predict_proba(X)
    proba = np.zeros((len(df), len(LABELS)))
    for col, cls in enumerate(clf.classes_):
        proba[:, int(cls)] = raw[:, col]
    return proba


def ece(conf, pred_i, y, bins=10):
    correct = (pred_i == y).astype(np.float64)
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (conf > lo) & (conf <= hi) if lo > 0 else (conf >= lo) & (conf <= hi)
        if mask.sum() == 0:
            continue
        total += mask.mean() * abs(correct[mask].mean() - conf[mask].mean())
    return float(total)


def eval_bundle(bundle, df, y, mult):
    proba = predict_proba(bundle, df)
    pred_i, conf = finalize_proba(
        proba, np.asarray(mult), bundle.get("reject_t", 0.0),
        bundle.get("confidence_temperature", 1.0))
    pairs = [(LABELS[int(e)], LABELS[int(p)]) for e, p in zip(y, pred_i)]
    metrics = compute_metrics(pairs)
    metrics.pop("confusion_matrix", None)
    metrics["ece"] = ece(conf, pred_i, y)
    return metrics


def honest_mask(df, excluded):
    return ~df["text"].astype(str).str.strip().isin(excluded).to_numpy()


def gate_verdict(candidate_macro, baseline_macro, tol):
    return "PASS" if candidate_macro >= baseline_macro - tol else "FAIL"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", default=os.path.join(BASE, "models/clf_v3.pkl"))
    ap.add_argument("--baseline", required=True,
                    help="对照模型, 如 models/clf_v3_baseline_v42.pkl")
    ap.add_argument("--candidate-manifest", default=None)
    ap.add_argument("--baseline-manifest", default=None)
    ap.add_argument("--val", default=os.path.join(FEAT_DIR, "val_feats.csv"))
    ap.add_argument("--test", default=os.path.join(FEAT_DIR, "test_feats.csv"))
    ap.add_argument("--splits", nargs="+", default=["val", "test"],
                    choices=["val", "test"])
    ap.add_argument("--tol", type=float, default=0.002,
                    help="允许的 shared macro-F1 回退 (默认 0.002)")
    ap.add_argument("--seed-band", type=float, default=0.004,
                    help="单 seed 噪声带 (默认 0.004; 实测 random_state 42→43 "
                         "在诚实子集上可达 0.0044). 仅用于提示, 不改变 verdict")
    ap.add_argument("--metric", choices=["shared", "own"], default="own",
                    help="门禁指标: own=各自乘数 (部署口径, 默认); "
                         "shared=同乘 baseline multipliers (跨校准方法时仅诊断)")
    ap.add_argument("--out", default=os.path.join(BASE, "output", "honest_gate.json"))
    args = ap.parse_args()

    print("== 模型 ==")
    cand = load_bundle(args.candidate)
    base = load_bundle(args.baseline)
    cman_path, cman = load_manifest(args.candidate, args.candidate_manifest)
    bman_path, bman = load_manifest(args.baseline, args.baseline_manifest)
    print(f"  candidate: {args.candidate}\n    manifest: {cman_path}")
    print(f"  baseline : {args.baseline}\n    manifest: {bman_path}")
    if list(cand["feature_names"]) != list(base["feature_names"]):
        raise SystemExit("candidate/baseline 特征列不一致")

    print("== 训练文本 (排除集) ==")
    excluded = manifest_train_texts(cman, "candidate") | manifest_train_texts(bman, "baseline")
    print(f"  排除集 union = {len(excluded):,} unique texts")

    shared_mult = np.asarray(base["multipliers"])
    result = {
        "candidate": {"path": args.candidate, "manifest": cman_path},
        "baseline": {"path": args.baseline, "manifest": bman_path},
        "excluded_texts": len(excluded),
        "tol": args.tol,
        "metric": args.metric,
        "splits": {},
    }
    deltas = {}
    for split in args.splits:
        path = args.val if split == "val" else args.test
        df = pd.read_csv(path)
        mask = honest_mask(df, excluded)
        y = df["label"].map(L2I).to_numpy()
        n_honest = int(mask.sum())
        if n_honest == 0:
            raise SystemExit(f"{split} 诚实子集为空")
        sub = df.loc[mask]
        ys = y[mask]
        print(f"\n== {split}: total={len(df):,} honest={n_honest:,} "
              f"({n_honest / len(df):.1%}) ==")
        row = {"n_total": int(len(df)), "n_honest": n_honest,
               "honest_frac": round(n_honest / len(df), 4), "models": {}}
        for label, bundle, own_mult in (
                ("baseline", base, np.asarray(base["multipliers"])),
                ("candidate", cand, np.asarray(cand["multipliers"]))):
            met_shared = eval_bundle(bundle, sub, ys, shared_mult)
            met_own = eval_bundle(bundle, sub, ys, own_mult)
            met_argmax = eval_bundle(bundle, sub, ys, np.ones(len(LABELS)))
            row["models"][label] = {
                "shared": met_shared, "own": met_own, "argmax": met_argmax,
                "multipliers": [float(x) for x in own_mult],
            }
            print(f"  {label:9s} shared={met_shared['macro_f1']:.4f} "
                  f"own={met_own['macro_f1']:.4f} argmax={met_argmax['macro_f1']:.4f} "
                  f"ECE(own)={met_own['ece']:.4f}")
            print("    per-class F1 (shared): " + "  ".join(
                f"{lb}={met_shared['per_class'][lb]['f1']:.3f}" for lb in LABELS))

        delta_shared = (row["models"]["candidate"]["shared"]["macro_f1"]
                        - row["models"]["baseline"]["shared"]["macro_f1"])
        delta_own = (row["models"]["candidate"]["own"]["macro_f1"]
                     - row["models"]["baseline"]["own"]["macro_f1"])
        row["delta_shared"] = round(delta_shared, 4)
        row["delta_own"] = round(delta_own, 4)
        deltas[split] = delta_shared if args.metric == "shared" else delta_own
        print(f"  delta({args.metric}) = {deltas[split]:+.4f}")
        result["splits"][split] = row

    verdict = "PASS"
    for split, d in deltas.items():
        if d < -args.tol:
            verdict = "FAIL"
    result["gate"] = {"verdict": verdict, "deltas": deltas,
                      "rule": f"{args.metric} macro-F1 >= baseline - {args.tol}",
                      "seed_band": args.seed_band}
    print(f"\n== GATE: {verdict} ({args.metric} macro-F1, tol={args.tol}) ==")
    for split, d in deltas.items():
        if abs(d) <= args.seed_band:
            print(f"  NOTE: {split} delta {d:+.4f} 在单 seed 噪声带 "
                  f"±{args.seed_band:.4f} 内; 判回归前至少复核 2-3 个 random_state")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"saved {args.out}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
