#!/usr/bin/env python3
"""org stats v3 — 用 v3 引擎 (v1.3.0) 替代硬编码 v1.1.1 识别器做 d1/d2/d3/d4 统计

用法: python tools/org_chunk_stats_v3.py <chunk.csv> <output.pkl>
"""
import os, sys, pickle
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import SegType
from core.config import BASE_DIR, ADDR_TYPES


def is_header(line: str) -> bool:
    return line.startswith("dict,") or line.startswith("dict\t")


def parse_text(line: str) -> str:
    return line.strip().rsplit(",", 5)[0].strip()


def clean_d2(text: str) -> str:
    for ch in '()（）[]【】{}':
        text = text.replace(ch, '')
    return text.strip()


def is_good_d2(text: str) -> bool:
    if not text or len(text) < 2:
        return False
    if text.isascii() and not any('一' <= c <= '鿿' for c in text):
        return False
    return True


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <chunk.csv> <output.pkl>", flush=True)
        sys.exit(1)
    inp, out_pkl = sys.argv[1], sys.argv[2]

    version = os.environ.get("STATS_VERSION")
    if not version:
        print("STATS_VERSION is required, e.g. STATS_VERSION=v1.4.3", file=sys.stderr)
        sys.exit(2)
    from v3.engine.configs import build_org_engine
    rec = build_org_engine(version)
    with open(os.path.join(BASE_DIR, "dicts", f"org_{version}.pkl"), "rb") as f:
        d3_set = set(pickle.load(f)["d3_freqs"])

    total = 0
    d1_freqs, d2_freqs, d3_freqs, d4_freqs = Counter(), Counter(), Counter(), Counter()
    d4_cats = Counter()
    seg_dist = Counter()
    d2_hit_total = d3_hit_total = d4_hit_total = 0

    basename = os.path.basename(inp)
    with open(inp, encoding="utf-8") as f:
        for line in f:
            if is_header(line):
                continue
            text = parse_text(line)
            if not text or len(text) < 2:
                continue
            total += 1
            res = rec.recognize(text)
            seg_dist[len(res.segments)] += 1
            for s in res.segments:
                if s.seg_type in ADDR_TYPES:
                    d1_freqs[s.text] += 1
                elif s.seg_type == SegType.POI:
                    d4_hit_total += 1
                    d4_freqs[s.text] += 1
                    if s.poi_type:
                        d4_cats[s.poi_type] += 1
                elif s.text in d3_set:
                    d3_hit_total += 1
                    d3_freqs[s.text] += 1
                elif s.seg_type in (SegType.UNKNOWN, SegType.BRAND):
                    cleaned = clean_d2(s.text)
                    if is_good_d2(cleaned):
                        d2_hit_total += 1
                        d2_freqs[cleaned] += 1
            if total % 1000000 == 0:
                print(f"  [{basename}] {total//10000}w d2={len(d2_freqs):,} "
                      f"d3={len(d3_freqs):,} d4={len(d4_freqs):,}", flush=True)

    stats = {
        "total": total, "total_unique": total,
        "d1_freqs": d1_freqs, "d2_freqs": d2_freqs,
        "d2_hit": d2_hit_total, "d3_hit": d3_hit_total, "d4_hit": d4_hit_total,
        "d3_freqs": d3_freqs, "d4_freqs": d4_freqs, "d4_cats": d4_cats,
        "seg_dist": seg_dist,
    }
    with open(out_pkl, "wb") as f:
        pickle.dump(stats, f)
    print(f"  [{os.path.basename(out_pkl)}] Done: {total:,}", flush=True)


if __name__ == "__main__":
    main()
