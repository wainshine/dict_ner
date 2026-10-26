#!/usr/bin/env python3
"""构建 v4.2.0 clean 训练集 final_train7 + held-out calib_feats。

流程:
  1. 读 group split 的 train/val/test 与基础 final_train6;
  2. 从 group train 的 unique text 随机 20% (seed=42) 划 calib;
  3. final_train7 = final_train6 去掉 val/test/calib 文本 + group train 中
     final_train6 未覆盖的缺失行特征;
  4. calib_feats = calib 行的特征 (与 final_train7 文本零重叠)。

用法:
  python3 v3/build_train7.py --split-prefix data/eval_split_group \
      --out-final output/v3_feat/final_train7.csv \
      --out-calib output/v3_feat/calib_feats.csv
  # 覆盖现役文件前加 --force (建议先手动备份)
"""
import argparse
import csv
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from v3.features import FEATURE_NAMES, FeatureExtractor

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEADER = ["text", "label", "source", "type_orig"] + FEATURE_NAMES
SPLITS = ("train", "val", "test")


def read_split(prefix, name):
    path = f"{prefix}_{name}.csv"
    with open(path, encoding="utf-8") as f:
        return [(r["text"].strip(), r["label"], r.get("source", ""))
                for r in csv.DictReader(f)]


def write_feats(rows, path, ex):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for text, label, source in rows:
            vec = ex.extract_vector(text)
            if len(vec) != len(FEATURE_NAMES):
                raise SystemExit(f"feature dim mismatch for {text!r}")
            w.writerow([text, label, source, ""] + vec)
            n += 1
            if n % 5000 == 0:
                print(f"  feats {os.path.basename(path)}: {n:,}", flush=True)
    print(f"  wrote {path} ({n:,} rows)", flush=True)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-final", default=os.path.join(BASE, "output/v3_feat/final_train6.csv"))
    ap.add_argument("--split-prefix", default=os.path.join(BASE, "data/eval_split"))
    ap.add_argument("--out-final", default=os.path.join(BASE, "output/v3_feat/final_train7.csv"))
    ap.add_argument("--out-calib", default=os.path.join(BASE, "output/v3_feat/calib_feats.csv"))
    ap.add_argument("--out-train-add", default=os.path.join(BASE, "output/v3_feat/train_add_feats.csv"))
    ap.add_argument("--calib-frac", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    for p in (args.out_final, args.out_calib, args.out_train_add):
        if os.path.exists(p) and not args.force:
            raise SystemExit(f"refuse to overwrite {p}; rerun with --force")

    train = read_split(args.split_prefix, "train")
    val = read_split(args.split_prefix, "val")
    test = read_split(args.split_prefix, "test")
    val_texts = set(r[0] for r in val)
    test_texts = set(r[0] for r in test)

    uniq = sorted(set(r[0] for r in train))
    random.Random(args.seed).shuffle(uniq)
    n_cal = max(1, round(len(uniq) * args.calib_frac))
    cal_texts = set(uniq[:n_cal])
    calib = [r for r in train if r[0] in cal_texts]
    exclude = val_texts | test_texts | cal_texts
    print(f"splits: train={len(train):,} val={len(val):,} test={len(test):,} "
          f"unique_train={len(uniq):,} calib_texts={len(cal_texts):,}")

    base_texts = set()
    tmp_final = args.out_final + ".tmp"
    kept = 0
    with open(args.base_final, encoding="utf-8", newline="") as fin, \
            open(tmp_final, "w", encoding="utf-8", newline="") as fout:
        r = csv.reader(fin)
        header = next(r)
        if header != HEADER:
            raise SystemExit("base final header does not match FEATURE_NAMES schema")
        w = csv.writer(fout)
        w.writerow(header)
        for row in r:
            text = row[0].strip()
            base_texts.add(text)
            if text in exclude:
                continue
            w.writerow(row)
            kept += 1
    print(f"base kept={kept:,} base_texts={len(base_texts):,}")

    train_add = [r for r in train if r[0] not in base_texts and r[0] not in cal_texts]
    print(f"train_add={len(train_add):,}; computing features...")
    ex = FeatureExtractor()
    n_calib = write_feats(calib, args.out_calib, ex)
    n_add = write_feats(train_add, args.out_train_add, ex)

    with open(args.out_train_add, encoding="utf-8", newline="") as fin, \
            open(tmp_final, "a", encoding="utf-8", newline="") as fout:
        r = csv.reader(fin)
        header2 = next(r)
        if header2 != HEADER:
            raise SystemExit("train_add feature header mismatch")
        w = csv.writer(fout)
        for row in r:
            w.writerow(row)
    os.replace(tmp_final, args.out_final)
    print(f"wrote {args.out_final} ({kept + n_add:,} rows)")

    final_texts = set()
    with open(args.out_final, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            final_texts.add(row["text"].strip())
    overlaps = {
        "val": len(final_texts & val_texts),
        "test": len(final_texts & test_texts),
        "calib": len(final_texts & cal_texts),
    }
    print(f"final rows={len(final_texts):,} overlap={overlaps}")
    if any(overlaps.values()):
        raise SystemExit(f"leakage detected: {overlaps}")

    meta = {
        "base_final": args.base_final,
        "split_prefix": args.split_prefix,
        "calib_frac": args.calib_frac,
        "seed": args.seed,
        "sizes": {"train": len(train), "val": len(val), "test": len(test)},
        "calib_texts": len(cal_texts),
        "calib_rows": n_calib,
        "train_add_rows": n_add,
        "final_rows": kept + n_add,
        "final_unique": len(final_texts),
        "overlap": overlaps,
    }
    meta_path = os.path.splitext(args.out_final)[0] + "_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"meta: {meta_path}")


if __name__ == "__main__":
    main()
