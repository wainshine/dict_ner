#!/usr/bin/env python3
"""POI 真错误模式增强采样 — 从 split/poi 抽取真错误簇样本, 标签 POI (D1-A)

数据源: data/split/poi/chunk_*.csv (name\tfreq, 全部 POI 语义)
防泄漏: 剔除与 eval val/test 重合文本 (复用 sample_pool 的 blocklist)
产出:   data/v3_augment_poi.csv (text,label)

用法: python3 v3/augment_poi.py [--per-pattern 3000]
"""
import argparse
import csv
import glob
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_CSV = os.path.join(BASE, "data", "v3_augment_poi.csv")

# 真错误簇 (v4_poi_recall_audit.md): 景区/寺山/广场/大厦/酒店/商超/门店
PATTERNS = {
    "景区": ("景区", "风景", "湿地", "森林"),
    "寺庙": ("寺", "庙"),
    "公园": ("公园",),
    "广场": ("广场",),
    "大厦": ("大厦",),
    "酒店": ("酒店", "宾馆", "饭店", "旅馆", "客栈"),
    "商超": ("超市", "商场", "百货", "市场"),
    "门店": ("网吧", "餐厅", "小吃", "理发", "美容", "洗车", "药店", "诊所"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-pattern", type=int, default=3000)
    args = ap.parse_args()

    from v3.sample_pool import load_eval_valtest_texts
    blocked = load_eval_valtest_texts()
    print(f"blocked val/test texts: {len(blocked):,}", flush=True)

    picked = defaultdict(set)   # pattern -> names
    chunks = sorted(glob.glob(os.path.join(BASE, "data", "split", "poi", "chunk_*.csv")))
    for ci, chunk in enumerate(chunks):
        if picked and all(len(picked[p]) >= args.per_pattern for p in PATTERNS):
            break
        with open(chunk, encoding="utf-8") as f:
            for line in f:
                name = line.rstrip("\n").split("\t")[0].strip()
                if len(name) < 3 or len(name) > 30 or name in blocked:
                    continue
                if re.search(r"[a-zA-Z]", name):
                    continue
                for pat, kws in PATTERNS.items():
                    if len(picked[pat]) >= args.per_pattern:
                        continue
                    if any(kw in name for kw in kws):
                        picked[pat].add(name)
                        break
        total = sum(len(v) for v in picked.values())
        print(f"[{os.path.basename(chunk)}] picked={total:,} "
              f"{ {k: len(v) for k, v in picked.items()} }", flush=True)

    rows = [(n, "POI") for names in picked.values() for n in sorted(names)]
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["text", "label"])
        w.writerows(rows)
    print(f"written {len(rows):,} → {OUT_CSV}")


if __name__ == "__main__":
    main()
