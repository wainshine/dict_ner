#!/usr/bin/env python3
"""Aggregate per-chunk org stats → pruned dictionary with versioning"""
import os, sys, pickle, csv as csv_mod
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import BASE_DIR, DICT_DIR, DATA_DIR, VERSION, NUM_CHUNKS
from tools.pipeline_base import aggregate_stats_files, export_d2_csv

STATS_DIR = DICT_DIR
OUT_DIR = os.path.join(STATS_DIR, f"iter_{VERSION}")

MANUAL_EXCLUDE_D4 = {
    "美家", "骨里香", "食府", "家宴",
    "汇", "馆", "坊", "斋", "屋", "栈", "舍", "堂",
}

POI_EXCLUDE_D4 = {
    "小吃", "快餐", "麻辣烫", "烧烤", "火锅", "私房菜",
    "商行", "车行", "专卖", "专柜", "批发", "批发部",
    "手机卖场", "报刊亭", "百货",
    "造型", "美发", "快递", "发艺", "KTV",
    "布艺", "窗帘", "童装", "家纺", "灯饰",
    "生活馆", "体验馆", "蛋糕房", "彩票",
    "客栈", "总代理", "总经销", "美容院", "发屋", "浴池",
    "美甲美睫", "批发零售", "儿童乐园", "小屋", "住宿",
    "经营部",
}

THRESHOLDS = {"d1": 5, "d3": 3, "d4": 100}

GOV_SEED = os.path.join(DATA_DIR, "gov_suffix_seed.csv")
GOV_SEED_FREQ = 50000


def merge_gov_seed(pruned):
    if not os.path.exists(GOV_SEED):
        return pruned, 0, 0
    d4 = dict(pruned["d4_freqs"])
    injected = 0
    boosted = 0
    with open(GOV_SEED, encoding="utf-8-sig") as f:
        for row in csv_mod.DictReader(f):
            sfx = row["suffix"].strip()
            if not sfx or len(sfx) < 2:
                continue
            old_freq = d4.get(sfx, 0)
            new_freq = max(old_freq, GOV_SEED_FREQ)
            if old_freq == 0:
                injected += 1
            elif new_freq > old_freq:
                boosted += 1
            d4[sfx] = new_freq
    pruned["d4_freqs"] = d4
    return pruned, injected, boosted


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
                continue  # malformed row: can't determine quality, skip
            quality[sfx] = {"com": com, "org": org, "loc": loc}
    return quality


def is_good_d4_suffix(sfx: str, freq: int, quality: dict) -> bool:
    if freq < THRESHOLDS["d4"]:
        return False
    if sfx in MANUAL_EXCLUDE_D4 or sfx in POI_EXCLUDE_D4:
        return False
    q = quality.get(sfx)
    if q is not None and q.get("loc", 0) > q.get("org", 0):
        return False
    return True


def prune(merged: dict, quality: dict) -> dict:
    d1 = {w: f for w, f in merged["d1_freqs"].items() if f >= THRESHOLDS["d1"]}
    d3 = {w: f for w, f in merged["d3_freqs"].items() if f >= THRESHOLDS["d3"]}
    d4 = {w: f for w, f in merged["d4_freqs"].items() if is_good_d4_suffix(w, f, quality)}
    return {"d1_freqs": d1, "d3_freqs": d3, "d4_freqs": d4}


def print_report(merged: dict, pruned: dict):
    total = merged["total"]
    print(f"\n{'='*60}", flush=True)
    print(f"ORG AGGREGATE {VERSION} ({total:,} records)", flush=True)
    print(f"{'='*60}", flush=True)

    print(f"\nStats:", flush=True)
    coverage = {
        "d1": len(merged["d1_freqs"]),
        "d2": len(merged["d2_freqs"]),
        "d3": len(merged["d3_freqs"]),
        "d4": len(merged["d4_freqs"]),
    }
    for k, v in coverage.items():
        print(f"  {k}: {v:>10,} unique (pruned→{len(pruned.get(k+'_freqs', {})):>6,})", flush=True)

    hit = {"d1": "-", "d2": merged["d2_hit"], "d3": merged["d3_hit"], "d4": merged["d4_hit"]}
    for k, v in hit.items():
        if v == "-":
            print(f"  {k}_hit: ---", flush=True)
        else:
            print(f"  {k}_hit: {v:>10,} ({100*v/total:.1f}%)", flush=True)

    print(f"\nPruned dict sizes:", flush=True)
    for k in ["d1_freqs", "d3_freqs", "d4_freqs"]:
        print(f"  {k}: {len(pruned[k]):>8,}", flush=True)

    print(f"\nSeg dist (top):", flush=True)
    for n, c in merged["seg_dist"].most_common(10):
        print(f"  {n}seg: {c:>12,} ({100*c/total:.1f}%)", flush=True)

    print(f"\nd4 Categories (top 15):", flush=True)
    for cat, cnt in merged["d4_cats"].most_common(15):
        print(f"  {cat:20s}: {cnt:>12,} ({100*cnt/total:.1f}%)", flush=True)


def main():
    quality = load_d444_quality(DATA_DIR)
    print(f"Loaded d444 quality data: {len(quality):,} suffixes", flush=True)

    stats_files = [os.path.join(STATS_DIR, f"iter_{VERSION}", f"org_stats_{i:02d}.pkl") for i in range(NUM_CHUNKS)]
    merged = aggregate_stats_files(stats_files)
    pruned = prune(merged, quality)
    pruned, gov_injected, gov_boosted = merge_gov_seed(pruned)
    print(f"Gov suffix seed: +{gov_injected} new, boosted {gov_boosted} existing "
          f"(total d4: {len(pruned['d4_freqs']):,})", flush=True)
    print_report(merged, pruned)

    os.makedirs(OUT_DIR, exist_ok=True)

    dict_path = os.path.join(STATS_DIR, f"org_{VERSION}.pkl")
    with open(dict_path, "wb") as f:
        pickle.dump(pruned, f)
    print(f"\nSaved: {dict_path} ({os.path.getsize(dict_path)/1024/1024:.1f}MB)", flush=True)

    merged_path = os.path.join(OUT_DIR, "org_merged_stats.pkl")
    with open(merged_path, "wb") as f:
        pickle.dump(merged, f)
    print(f"Saved: {merged_path}", flush=True)

    csv_path = os.path.join(OUT_DIR, f"org_d2_freqs_{VERSION}.csv")
    export_d2_csv(merged["d2_freqs"], csv_path)


if __name__ == "__main__":
    main()
