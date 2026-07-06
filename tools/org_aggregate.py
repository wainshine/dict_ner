#!/usr/bin/env python3
"""Aggregate per-chunk org stats → pruned dictionary with versioning"""
import os, sys, pickle, csv as csv_mod
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VERSION = "v1.1.1"
NUM_CHUNKS = 16
STATS_DIR = os.path.join(BASE, "dicts")
DATA_DIR = os.path.join(BASE, "data")
OUT_DIR = os.path.join(STATS_DIR, f"iter_{VERSION}")

MANUAL_EXCLUDE_D4 = {
    "美家", "骨里香", "食府", "家宴",
    "汇", "馆", "坊", "斋", "屋", "栈", "舍", "堂",
}

THRESHOLDS = {"d1": 5, "d3": 3, "d4": 100}


def load_d444_quality(data_dir: str) -> dict:
    """Load per-suffix org/loc/com counts from d444 for quality filtering."""
    path = os.path.join(data_dir, "suffix_segments_sql.csv")
    quality = {}
    with open(path, encoding="utf-8-sig") as f:
        for row in csv_mod.DictReader(f):
            sfx = row["d4"].strip()
            if not sfx or len(sfx) < 2:
                continue
            try:
                com = int(row.get("com", 0) or 0)
                org = int(row.get("org", 0) or 0)
                loc = int(row.get("loc", 0) or 0)
            except (ValueError, KeyError):
                com = org = loc = 0
            quality[sfx] = {"com": com, "org": org, "loc": loc}
    return quality


def is_good_d4_suffix(sfx: str, freq: int, quality: dict) -> bool:
    if freq < THRESHOLDS["d4"]:
        return False
    if sfx in MANUAL_EXCLUDE_D4:
        return False
    q = quality.get(sfx, {})
    if q.get("loc", 0) > q.get("org", 0):
        return False
    return True


def aggregate(stats_files: list, quality: dict):
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


def prune(merged: dict, quality: dict) -> dict:
    d1 = {w: f for w, f in merged["d1_freqs"].items() if f >= THRESHOLDS["d1"]}
    d3 = {w: f for w, f in merged["d3_freqs"].items() if f >= THRESHOLDS["d3"]}
    d4 = {w: f for w, f in merged["d4_freqs"].items() if is_good_d4_suffix(w, f, quality)}
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
    print(f"ORG AGGREGATE {VERSION} ({total:,} records)")
    print(f"{'='*60}")

    print(f"\nStats:")
    coverage = {
        "d1": len(merged["d1_freqs"]),
        "d2": len(merged["d2_freqs"]),
        "d3": len(merged["d3_freqs"]),
        "d4": len(merged["d4_freqs"]),
    }
    for k, v in coverage.items():
        print(f"  {k}: {v:>10,} unique (pruned→{len(pruned.get(k+'_freqs', {})):>6,})")

    hit = {"d1": "-", "d2": merged["d2_hit"], "d3": merged["d3_hit"], "d4": merged["d4_hit"]}
    for k, v in hit.items():
        if v == "-":
            print(f"  {k}_hit: ---")
        else:
            print(f"  {k}_hit: {v:>10,} ({100*v/total:.1f}%)")

    print(f"\nPruned dict sizes:")
    for k in ["d1_freqs", "d3_freqs", "d4_freqs"]:
        print(f"  {k}: {len(pruned[k]):>8,}")

    print(f"\nSeg dist (top):")
    for n, c in merged["seg_dist"].most_common(10):
        print(f"  {n}seg: {c:>12,} ({100*c/total:.1f}%)")

    print(f"\nd4 Categories (top 15):")
    for cat, cnt in merged["d4_cats"].most_common(15):
        print(f"  {cat:20s}: {cnt:>12,} ({100*cnt/total:.1f}%)")


def main():
    quality = load_d444_quality(DATA_DIR)
    print(f"Loaded d444 quality data: {len(quality):,} suffixes", flush=True)

    stats_files = [os.path.join(STATS_DIR, f"iter_{VERSION}", f"org_stats_{i:02d}.pkl") for i in range(NUM_CHUNKS)]
    merged = aggregate(stats_files, quality)
    pruned = prune(merged, quality)
    print_report(merged, pruned)

    os.makedirs(OUT_DIR, exist_ok=True)

    dict_path = os.path.join(STATS_DIR, f"org_{VERSION}.pkl")
    with open(dict_path, "wb") as f:
        pickle.dump(pruned, f)
    print(f"\nSaved: {dict_path} ({os.path.getsize(dict_path)/1024/1024:.1f}MB)")

    merged_path = os.path.join(OUT_DIR, "org_merged_stats.pkl")
    with open(merged_path, "wb") as f:
        pickle.dump(merged, f)
    print(f"Saved: {merged_path}")

    csv_path = os.path.join(OUT_DIR, f"org_d2_freqs_{VERSION}.csv")
    export_d2_csv(merged["d2_freqs"], csv_path)


if __name__ == "__main__":
    main()
