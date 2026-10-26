#!/usr/bin/env python3
"""真实 UNKNOWN 采样 — 高德室内设施 + 腾讯公交线编号 → data/v3_unknown_pool.csv

标签定义: 室内设施(会议室/桌号/摊位)与公交线编号(房20/顺34) → UNKNOWN (非独立实体)。
防泄漏: 剔除已在 eval val/test 及合成 UNKNOWN 中的文本。
用法: python v3/sample_unknown.py [--gaode 23000]
产出: data/v3_unknown_pool.csv (text,label,source,type_orig)
"""
import argparse
import csv
import os
import random
import sys

csv.field_size_limit(sys.maxsize)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import DATA_DIR
from tools.build_eval_set import _safe_text

GAODE_DIR = os.path.join(DATA_DIR, "高德amap")
TENCENT_DIR = os.path.join(DATA_DIR, "腾讯地图")
OUT = os.path.join(DATA_DIR, "v3_unknown_pool.csv")


def load_blocked():
    blocked = set()
    for name in ("eval_split_val.csv", "eval_split_test.csv"):
        path = os.path.join(DATA_DIR, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    blocked.add(row["text"].strip())
    synth = os.path.join(DATA_DIR, "v3_synth_unknown.csv")
    if os.path.exists(synth):
        with open(synth, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                blocked.add(row["text"].strip())
    return blocked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gaode", type=int, default=23000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    random.seed(args.seed)

    blocked = load_blocked()
    print(f"blocked: {len(blocked):,}")

    indoor = []
    indoor_seen = 0
    files = sorted(f for f in os.listdir(GAODE_DIR) if f.endswith(".csv"))
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
                typ = (row[9] or "").strip()
                if typ.split(";")[0] != "室内设施":
                    continue
                text = _safe_text(row[6])
                if not text or text in blocked:
                    continue
                if indoor_seen < args.gaode:
                    indoor.append((text, "UNKNOWN", "gaode_indoor", "室内设施"))
                else:
                    j = random.randint(0, indoor_seen)
                    if j < args.gaode:
                        indoor[j] = (text, "UNKNOWN", "gaode_indoor", "室内设施")
                indoor_seen += 1
        if (i + 1) % 20 == 0:
            print(f"  gaode {i+1}/{len(files)}, indoor {len(indoor):,}", flush=True)
    print(f"indoor: {len(indoor):,}", flush=True)

    bus = []
    tfiles = sorted(f for f in os.listdir(TENCENT_DIR) if f.endswith(".csv"))
    for fname in tfiles:
        path = os.path.join(TENCENT_DIR, fname)
        with open(path, encoding="gbk", errors="replace") as f:
            for row in csv.reader(f):
                if len(row) < 7:
                    continue
                if (row[6] or "").strip().split(";")[0] != "公交线编号":
                    continue
                text = _safe_text(row[1])
                if text and text not in blocked:
                    bus.append((text, "UNKNOWN", "tencent_busline", "公交线编号"))
    print(f"busline: {len(bus):,}", flush=True)

    rows = indoor + bus
    seen = set()
    deduped = []
    for r in rows:
        if r[0] in seen:
            continue
        seen.add(r[0])
        deduped.append(r)
    random.shuffle(deduped)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["text", "label", "source", "type_orig"])
        w.writerows(deduped)
    print(f"total: {len(deduped):,} -> {OUT}")


if __name__ == "__main__":
    main()
