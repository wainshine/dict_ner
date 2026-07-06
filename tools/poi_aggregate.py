#!/usr/bin/env python3
"""Aggregate per-chunk POI stats → pruned POI dictionary"""
import os, sys, pickle, csv as csv_mod
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VERSION = "v1.1.1"
NUM_CHUNKS = 16
STATS_DIR = os.path.join(BASE, "dicts")
DATA_DIR = os.path.join(BASE, "data")
OUT_DIR = os.path.join(STATS_DIR, f"iter_{VERSION}")

THRESHOLDS = {"d1": 5, "d3": 10, "d4": 100}

GENERIC_D1_BLACKLIST = {
    "社区", "街道", "小区", "服务区", "校区", "新区", "开发区",
    "平安", "幸福", "阳光", "东方", "凤凰", "新华", "金山", "远景",
    "南方", "北方", "中心", "广场", "花园", "大厦",
}


def load_poi_seed(data_dir: str) -> set:
    path = os.path.join(data_dir, "..", "dicts", "suffix_seed.csv")
    if not os.path.exists(path):
        path = os.path.join(BASE, "dicts", "suffix_seed.csv")
    seed = set()
    with open(path, encoding="utf-8") as f:
        for row in csv_mod.DictReader(f):
            sfx = row["sfx"].strip()
            if sfx and len(sfx) >= 2:
                seed.add(sfx)
    return seed


def aggregate(stats_files: list):
    merged = Counter()
    d1_freqs = Counter()
    d2_freqs = Counter()
    d3_freqs = Counter()
    d4_freqs = Counter()
    d4_cats = Counter()
    seg_dist = Counter()
    total = 0
    d2_hit = d3_hit = d4_hit = 0

    for path in stats_files:
        if not os.path.exists(path):
            print(f"  MISSING: {path}", flush=True)
            continue
        with open(path, "rb") as f:
            s = pickle.load(f)
        total += s["total"]
        d2_hit += s.get("d2_hit", 0)
        d3_hit += s.get("d3_hit", 0)
        d4_hit += s.get("d4_hit", 0)
        d1_freqs += s.get("d1_freqs", Counter())
        d2_freqs += s.get("d2_freqs", Counter())
        d3_freqs += s.get("d3_freqs", Counter())
        d4_freqs += s.get("d4_freqs", Counter())
        d4_cats += s.get("d4_cats", Counter())
        seg_dist += s.get("seg_dist", Counter())

    return {
        "total": total, "d2_hit": d2_hit, "d3_hit": d3_hit, "d4_hit": d4_hit,
        "d1_freqs": d1_freqs, "d2_freqs": d2_freqs,
        "d3_freqs": d3_freqs, "d4_freqs": d4_freqs,
        "d4_cats": d4_cats, "seg_dist": seg_dist,
    }


def prune(merged: dict, poi_seed: set) -> dict:
    d1 = {w: f for w, f in merged["d1_freqs"].items()
          if f >= THRESHOLDS["d1"] and w not in GENERIC_D1_BLACKLIST}
    d3 = {w: f for w, f in merged["d3_freqs"].items() if f >= THRESHOLDS["d3"]}
    d4 = {w: f for w, f in merged["d4_freqs"].items()
          if f >= THRESHOLDS["d4"] and w in poi_seed}
    return {"d1_freqs": d1, "d3_freqs": d3, "d4_freqs": d4}


def export_d2_csv(d2_freqs: Counter, out_path: str):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv_mod.writer(f)
        w.writerow(["d2_text", "freq"])
        for text, freq in d2_freqs.most_common():
            w.writerow([text, freq])
    mb = os.path.getsize(out_path) / 1024 / 1024
    print(f"  Exported d2 CSV: {out_path} ({mb:.1f}MB, {len(d2_freqs):,} unique)")


def print_report(merged: dict, pruned: dict):
    total = merged["total"]
    print(f"\n{'='*60}")
    print(f"POI AGGREGATE {VERSION} ({total:,} records)")
    print(f"{'='*60}")

    print(f"\nStats:")
    for k in ["d1_freqs", "d2_freqs", "d3_freqs", "d4_freqs"]:
        label = k.replace("_freqs", "")
        raw = len(merged.get(k, {}))
        pr = len(pruned.get(k, {}))
        print(f"  {label}: {raw:>10,} raw → {pr:>8,} pruned")

    hit = {"d2": merged["d2_hit"], "d3": merged["d3_hit"], "d4": merged["d4_hit"]}
    for k, v in hit.items():
        print(f"  {k}_hit: {v:>10,} ({100*v/total:.1f}%)")

    print(f"\nSeg dist (top):")
    for n, c in merged["seg_dist"].most_common(10):
        print(f"  {n}seg: {c:>12,} ({100*c/total:.1f}%)")

    print(f"\nPOI d4 Categories (top 20):")
    for cat, cnt in merged["d4_cats"].most_common(20):
        print(f"  {cat:20s}: {cnt:>12,} ({100*cnt/total:.1f}%)")


def main():
    seed = load_poi_seed(DATA_DIR)
    print(f"Loaded POI seed: {len(seed):,} suffixes", flush=True)

    stats_files = [os.path.join(STATS_DIR, f"iter_{VERSION}", f"poi_stats_{i:02d}.pkl") for i in range(NUM_CHUNKS)]
    merged = aggregate(stats_files)
    pruned = prune(merged, seed)
    print_report(merged, pruned)

    os.makedirs(OUT_DIR, exist_ok=True)

    dict_path = os.path.join(STATS_DIR, f"poi_{VERSION}.pkl")
    with open(dict_path, "wb") as f:
        pickle.dump(pruned, f)
    print(f"\nSaved: {dict_path} ({os.path.getsize(dict_path)/1024/1024:.1f}MB)")

    merged_path = os.path.join(OUT_DIR, "poi_merged_stats.pkl")
    with open(merged_path, "wb") as f:
        pickle.dump(merged, f)
    print(f"Saved: {merged_path}")

    csv_path = os.path.join(OUT_DIR, f"poi_d2_freqs_{VERSION}.csv")
    export_d2_csv(merged["d2_freqs"], csv_path)


if __name__ == "__main__":
    main()
