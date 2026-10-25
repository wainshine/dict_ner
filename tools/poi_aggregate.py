#!/usr/bin/env python3
"""Aggregate per-chunk POI stats → pruned POI dictionary"""
import os, sys, csv as csv_mod
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import BASE_DIR, DICT_DIR, DATA_DIR, VERSION as _VERSION, NUM_CHUNKS
VERSION = os.environ.get("DICT_VERSION", _VERSION)
from tools.pipeline_base import aggregate_stats_files, export_d2_csv, atomic_pickle_dump

STATS_DIR = DICT_DIR
OUT_DIR = os.path.join(STATS_DIR, f"iter_{VERSION}")

THRESHOLDS = {"d1": 5, "d3": 10, "d4": 100}
POI_SEED_FREQ = 50000

POI_OVERRIDE_SUFFIXES = {
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

GENERIC_D1_BLACKLIST = {
    "社区", "街道", "小区", "服务区", "校区", "新区", "开发区",
    "平安", "幸福", "阳光", "东方", "凤凰", "新华", "金山", "远景",
    "南方", "北方", "中心", "广场", "花园", "大厦",
}


def load_poi_seed(data_dir: str) -> set:
    path = os.path.join(data_dir, "suffix_seed.csv")
    if not os.path.exists(path):
        path = os.path.join(BASE_DIR, "data", "suffix_seed.csv")
    seed = set()
    with open(path, encoding="utf-8") as f:
        for row in csv_mod.DictReader(f):
            sfx = row["sfx"].strip()
            if sfx and len(sfx) >= 2:
                seed.add(sfx)
    return seed


def prune(merged: dict, poi_seed: set) -> dict:
    d1 = {w: f for w, f in merged["d1_freqs"].items()
          if f >= THRESHOLDS["d1"] and w not in GENERIC_D1_BLACKLIST}
    d3 = {w: f for w, f in merged["d3_freqs"].items() if f >= THRESHOLDS["d3"]}
    d4 = {w: f for w, f in merged["d4_freqs"].items()
          if f >= THRESHOLDS["d4"] and w in poi_seed}
    return {"d1_freqs": d1, "d3_freqs": d3, "d4_freqs": d4}


def merge_poi_overrides(pruned):
    d4 = dict(pruned["d4_freqs"])
    injected = 0
    boosted = 0
    for sfx in POI_OVERRIDE_SUFFIXES:
        old_freq = d4.get(sfx, 0)
        new_freq = max(old_freq, POI_SEED_FREQ)
        if old_freq == 0:
            injected += 1
        elif new_freq > old_freq:
            boosted += 1
        d4[sfx] = new_freq
    pruned["d4_freqs"] = d4
    return pruned, injected, boosted


def print_report(merged: dict, pruned: dict):
    total = merged["total"]
    print(f"\n{'='*60}", flush=True)
    print(f"POI AGGREGATE {VERSION} ({total:,} records)", flush=True)
    print(f"{'='*60}", flush=True)

    print(f"\nStats:", flush=True)
    for k in ["d1_freqs", "d2_freqs", "d3_freqs", "d4_freqs"]:
        label = k.replace("_freqs", "")
        raw = len(merged.get(k, {}))
        pr = len(pruned.get(k, {}))
        print(f"  {label}: {raw:>10,} raw → {pr:>8,} pruned", flush=True)

    hit = {"d2": merged["d2_hit"], "d3": merged["d3_hit"], "d4": merged["d4_hit"]}
    for k, v in hit.items():
        print(f"  {k}_hit: {v:>10,} ({100*v/total:.1f}%)", flush=True)

    print(f"\nSeg dist (top):", flush=True)
    for n, c in merged["seg_dist"].most_common(10):
        print(f"  {n}seg: {c:>12,} ({100*c/total:.1f}%)", flush=True)

    print(f"\nPOI d4 Categories (top 20):", flush=True)
    for cat, cnt in merged["d4_cats"].most_common(20):
        print(f"  {cat:20s}: {cnt:>12,} ({100*cnt/total:.1f}%)", flush=True)


def main():
    seed = load_poi_seed(DATA_DIR)
    print(f"Loaded POI seed: {len(seed):,} suffixes", flush=True)

    stats_files = [os.path.join(STATS_DIR, f"iter_{VERSION}", f"poi_stats_{i:02d}.pkl") for i in range(NUM_CHUNKS)]
    missing = [p for p in stats_files if not os.path.exists(p)]
    if missing:
        print(f"Missing {len(missing)}/{NUM_CHUNKS} poi stats files, abort:", flush=True)
        for p in missing[:5]:
            print(f"  {p}", flush=True)
        raise SystemExit(1)
    merged = aggregate_stats_files(stats_files)
    pruned = prune(merged, seed)
    pruned, poi_injected, poi_boosted = merge_poi_overrides(pruned)
    print(f"POI override seed: +{poi_injected} new, boosted {poi_boosted} existing "
          f"(total d4: {len(pruned['d4_freqs']):,})", flush=True)
    print_report(merged, pruned)

    os.makedirs(OUT_DIR, exist_ok=True)

    dict_path = os.path.join(STATS_DIR, f"poi_{VERSION}.pkl")
    atomic_pickle_dump(pruned, dict_path)
    print(f"\nSaved: {dict_path} ({os.path.getsize(dict_path)/1024/1024:.1f}MB)", flush=True)

    merged_path = os.path.join(OUT_DIR, "poi_merged_stats.pkl")
    atomic_pickle_dump(merged, merged_path, backup=False)
    print(f"Saved: {merged_path}", flush=True)

    csv_path = os.path.join(OUT_DIR, f"poi_d2_freqs_{VERSION}.csv")
    export_d2_csv(merged["d2_freqs"], csv_path)


if __name__ == "__main__":
    main()
