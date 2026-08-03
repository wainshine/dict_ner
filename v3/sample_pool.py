#!/usr/bin/env python3
"""大语料弱标注采样 — Gaode 2M + Tencent 1M → data/v3_train_pool.csv

复用 build_eval_set 的 type→4类映射。剔除与 eval val/test 重合的文本(防泄漏)。
用法: python v3/sample_pool.py [--gaode 2000000] [--tencent 1000000]
"""
import argparse
import csv
import os
import random
import sys

csv.field_size_limit(sys.maxsize)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import DATA_DIR
from tools.build_eval_set import (
    GAODE_TYPE_MAP, GAODE_SKIP_TYPES, TENCENT_TYPE_MAP, TENCENT_SKIP_TYPES,
    _safe_text,
)

GAODE_DIR = os.path.join(DATA_DIR, "高德amap")
TENCENT_DIR = os.path.join(DATA_DIR, "腾讯地图")
OUT_PATH = os.path.join(DATA_DIR, "v3_train_pool.csv")


def load_eval_valtest_texts():
    blocked = set()
    for name in ("eval_split_val.csv", "eval_split_test.csv"):
        path = os.path.join(DATA_DIR, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                blocked.add(row["text"].strip())
    return blocked


def sample_gaode(target_total, blocked):
    files = sorted(f for f in os.listdir(GAODE_DIR) if f.endswith(".csv"))
    type_counts = {}
    total_valid = 0
    for fname in files:
        path = os.path.join(GAODE_DIR, fname)
        if os.path.getsize(path) == 0:
            continue
        with open(path, encoding="gbk", errors="replace") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) < 10:
                    continue
                typ = (row[9] or "").strip()
                t1 = typ.split(";")[0] if typ else ""
                if not t1 or t1 in GAODE_SKIP_TYPES or t1 not in GAODE_TYPE_MAP:
                    continue
                if "自动提款机" in typ or "自助银行" in typ:
                    continue
                if not (row[6] or "").strip():
                    continue
                type_counts[t1] = type_counts.get(t1, 0) + 1
                total_valid += 1
    type_targets = {t: max(100, round(target_total * c / total_valid))
                    for t, c in type_counts.items()}
    print(f"Gaode pass1: {total_valid:,} valid, {len(type_targets)} types", flush=True)

    samples_by_type = {t: [] for t in type_targets}
    for i, fname in enumerate(files):
        path = os.path.join(GAODE_DIR, fname)
        if os.path.getsize(path) == 0:
            continue
        with open(path, encoding="gbk", errors="replace") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) < 10:
                    continue
                text = _safe_text(row[6])
                if not text or text in blocked:
                    continue
                typ = (row[9] or "").strip()
                t1 = typ.split(";")[0] if typ else ""
                if not t1 or t1 in GAODE_SKIP_TYPES:
                    continue
                label = GAODE_TYPE_MAP.get(t1)
                if label is None:
                    continue
                if "自动提款机" in typ or "自助银行" in typ:
                    continue
                buf = samples_by_type.get(t1)
                if buf is None:
                    continue
                target = type_targets[t1]
                item = (text, label, "gaode", t1)
                if len(buf) < target:
                    buf.append(item)
                else:
                    j = random.randint(0, len(buf) - 1)
                    if j < target:
                        buf[j] = item
        if (i + 1) % 10 == 0:
            print(f"  gaode pass2: {i+1}/{len(files)} files", flush=True)

    results = []
    for t, samples in sorted(samples_by_type.items()):
        results.extend(samples)
    print(f"Gaode: {len(results):,} samples", flush=True)
    return results


def sample_tencent(target_total, blocked):
    files = [f for f in os.listdir(TENCENT_DIR) if f.endswith(".csv")]
    total_size = sum(os.path.getsize(os.path.join(TENCENT_DIR, f)) for f in files)
    results = []
    for i, fname in enumerate(files):
        path = os.path.join(TENCENT_DIR, fname)
        target = max(50, round(target_total * os.path.getsize(path) / total_size))
        samples = []
        with open(path, encoding="gbk", errors="replace") as f:
            for row in csv.reader(f):
                if len(row) < 7:
                    continue
                text = _safe_text(row[1])
                if not text or text in blocked:
                    continue
                cat_raw = (row[6] or "").strip()
                cat_1st = cat_raw.split(";")[0] if cat_raw else ""
                if not cat_1st or cat_1st in TENCENT_SKIP_TYPES:
                    continue
                label = TENCENT_TYPE_MAP.get(cat_1st)
                if label is None:
                    continue
                samples.append((text, label, "tencent", cat_1st))
        if len(samples) > target:
            samples = random.sample(samples, target)
        results.extend(samples)
        if (i + 1) % 50 == 0:
            print(f"  tencent: {i+1}/{len(files)} files, {len(results):,} so far", flush=True)
    print(f"Tencent: {len(results):,} samples", flush=True)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gaode", type=int, default=2_000_000)
    ap.add_argument("--tencent", type=int, default=1_000_000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=OUT_PATH)
    args = ap.parse_args()
    random.seed(args.seed)

    blocked = load_eval_valtest_texts()
    print(f"Blocked {len(blocked):,} val/test texts", flush=True)

    results = sample_gaode(args.gaode, blocked) + sample_tencent(args.tencent, blocked)
    seen = set()
    deduped = []
    for item in results:
        if item[0] in seen:
            continue
        seen.add(item[0])
        deduped.append(item)
    random.shuffle(deduped)

    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["text", "label", "source", "type_orig"])
        w.writerows(deduped)
    from collections import Counter
    print(f"Total: {len(deduped):,} -> {args.out}")
    print("Label dist:", dict(Counter(r[1] for r in deduped)))


if __name__ == "__main__":
    main()
