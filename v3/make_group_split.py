#!/usr/bin/env python3
"""文本分组切分 — 同一文本只落一个 split, 消除 train/test 文本泄漏。

用法:
  python3 v3/make_group_split.py \
      --inputs data/eval_split_train.csv data/eval_split_val.csv data/eval_split_test.csv \
      --out-prefix data/eval_split_group
  # 可选: --install 同时备份并覆盖 data/eval_split_{train,val,test}.csv

方法: StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed), group=text;
      fold 0-2 = train (fold-major 顺序), fold 3 = val, fold 4 = test.
输入/输出列: text,label,source (与现有 eval_split 一致)。
"""
import argparse
import csv
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sklearn.model_selection import StratifiedGroupKFold

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPLITS = ("train", "val", "test")


def load_rows(paths):
    rows = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                text = (r.get("text") or "").strip()
                label = (r.get("label") or "").strip()
                if not text or not label:
                    continue
                rows.append((text, label, (r.get("source") or "").strip()))
    return rows


def group_split(rows, seed=42):
    texts = [r[0] for r in rows]
    labels = [r[1] for r in rows]
    if not rows:
        raise SystemExit("no rows to split")
    skf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    folds = [None] * len(rows)
    for k, (_, test_idx) in enumerate(skf.split(texts, labels, groups=texts)):
        for i in test_idx:
            folds[i] = k
    if any(f is None for f in folds):
        raise SystemExit("internal error: some rows not assigned to a fold")
    buckets = {k: [] for k in range(5)}
    for r, fold in zip(rows, folds):
        buckets[fold].append(r)
    parts = {name: [] for name in SPLITS}
    for fold in range(5):
        if fold <= 2:
            parts["train"].extend(buckets[fold])
        elif fold == 3:
            parts["val"].extend(buckets[fold])
        else:
            parts["test"].extend(buckets[fold])
    return parts


def check_disjoint(parts):
    sets = {name: set(r[0] for r in rows) for name, rows in parts.items()}
    overlaps = {
        "train-val": len(sets["train"] & sets["val"]),
        "train-test": len(sets["train"] & sets["test"]),
        "val-test": len(sets["val"] & sets["test"]),
    }
    return sets, overlaps


def write_part(path, rows):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["text", "label", "source"])
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs=3, default=[
        os.path.join(BASE, "data", "eval_split_train.csv"),
        os.path.join(BASE, "data", "eval_split_val.csv"),
        os.path.join(BASE, "data", "eval_split_test.csv"),
    ], metavar=("TRAIN", "VAL", "TEST"))
    ap.add_argument("--out-prefix", default=os.path.join(BASE, "data", "eval_split_group"))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--install", action="store_true",
                    help="备份并覆盖 data/eval_split_{train,val,test}.csv")
    ap.add_argument("--backup-suffix", default=".bak_v42")
    args = ap.parse_args()

    rows = load_rows(args.inputs)
    parts = group_split(rows, args.seed)
    sets, overlaps = check_disjoint(parts)
    print(f"rows={len(rows):,} unique={len(set(r[0] for r in rows)):,}")
    for name in SPLITS:
        print(f"  {name}: {len(parts[name]):,}")
    print(f"  text overlap: {overlaps}")
    if any(overlaps.values()):
        raise SystemExit("group split still has text overlap")

    out_paths = {name: f"{args.out_prefix}_{name}.csv" for name in SPLITS}
    for name in SPLITS:
        write_part(out_paths[name], parts[name])
        print(f"  wrote {out_paths[name]}")

    if args.install:
        for name in SPLITS:
            dst = os.path.join(BASE, "data", f"eval_split_{name}.csv")
            if os.path.exists(dst):
                bak = dst + args.backup_suffix
                if not os.path.exists(bak):
                    shutil.copy2(dst, bak)
                    print(f"  backup {bak}")
            shutil.copy2(out_paths[name], dst)
            print(f"  installed {dst}")

    report = {
        "inputs": args.inputs,
        "seed": args.seed,
        "method": "StratifiedGroupKFold(5, group=text)",
        "rows": len(rows),
        "unique_texts": len(set(r[0] for r in rows)),
        "sizes": {name: len(parts[name]) for name in SPLITS},
        "overlap": overlaps,
        "installed": bool(args.install),
    }
    report_path = args.out_prefix + "_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"report: {report_path}")


if __name__ == "__main__":
    main()
