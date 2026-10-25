#!/usr/bin/env python3
"""poi stats v3 — 用 v3 引擎 (poi_v1.3.0) 替代 poi_v1.1.2 识别器做 d1/d2/d3/d4 统计

用法: python tools/poi_chunk_stats_v3.py <chunk.csv> <output.pkl>
"""
import os, sys, re, pickle
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import SegType
from core.config import BASE_DIR, ADDR_TYPES


def clean_d2(text: str) -> str:
    for ch in '()（）[]【】{}':
        text = text.replace(ch, '')
    return text.strip()


def is_good_d2(text: str) -> bool:
    if not text or len(text) < 2:
        return False
    if text.isascii() and not any('一' <= c <= '鿿' for c in text):
        return False
    if re.match(r'.*[路街巷道]与$', text):
        return False
    if text.endswith('号楼'):
        return False
    if text in ('交叉口', '交汇处', '十字路口', '丁字路口', '交叉路口', '三岔路口'):
        return False
    if text == '中国':
        return False
    if re.match(r'.*[0-9A-Za-z][栋幢座]$', text):
        return False
    if text.endswith('小时') or text in ('昼夜', '通宵', '全天', '夜间'):
        return False
    if text in ('中共', '党委', '党组', '总支', '支部', '纪委', '人大', '政协'):
        return False
    if re.match(r'^第[一二三四五六七八九十百千万]+$', text):
        return False
    if text.endswith('梯') and len(text) <= 4:
        return False
    if re.match(r'^[A-Za-z0-9]+区$', text):
        return False
    if re.match(r'^[0-9]+店$', text):
        return False
    if re.match(r'^[0-9A-Za-z]+层$', text):
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
    from v3.engine.configs import build_poi_engine
    rec = build_poi_engine(f"poi_{version}.pkl")
    with open(os.path.join(BASE_DIR, "dicts", f"poi_{version}.pkl"), "rb") as f:
        d3_set = set(pickle.load(f)["d3_freqs"])

    d1_freqs, d2_freqs, d3_freqs, d4_freqs = Counter(), Counter(), Counter(), Counter()
    d4_cats = Counter()
    seg_dist = Counter()
    d2_hit_total = d3_hit_total = d4_hit_total = 0
    total_unique = total_weighted = 0

    basename = os.path.basename(inp)
    with open(inp, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.rsplit('\t', 1)
            if len(parts) == 2:
                text = parts[0]
                try:
                    weight = int(parts[1])
                except ValueError:
                    weight = 1
            else:
                text, weight = line, 1
            if not text or len(text) < 2:
                continue
            total_unique += 1
            total_weighted += weight
            res = rec.recognize(text)
            seg_dist[len(res.segments)] += weight
            for s in res.segments:
                if s.seg_type in ADDR_TYPES:
                    d1_freqs[s.text] += weight
                elif s.seg_type == SegType.POI:
                    d4_hit_total += weight
                    d4_freqs[s.text] += weight
                    if s.poi_type:
                        d4_cats[s.poi_type] += weight
                elif s.text in d3_set:
                    d3_hit_total += weight
                    d3_freqs[s.text] += weight
                elif s.seg_type in (SegType.UNKNOWN, SegType.BRAND):
                    cleaned = clean_d2(s.text)
                    if is_good_d2(cleaned):
                        d2_hit_total += weight
                        d2_freqs[cleaned] += weight
            if total_unique % 1000000 == 0:
                print(f"  [{basename}] {total_unique//10000}w d2={len(d2_freqs):,} "
                      f"d3={len(d3_freqs):,} d4={len(d4_freqs):,}", flush=True)

    stats = {
        "total": total_weighted, "total_unique": total_unique,
        "d1_freqs": d1_freqs, "d2_freqs": d2_freqs,
        "d2_hit": d2_hit_total, "d3_hit": d3_hit_total, "d4_hit": d4_hit_total,
        "d3_freqs": d3_freqs, "d4_freqs": d4_freqs, "d4_cats": d4_cats,
        "seg_dist": seg_dist,
    }
    with open(out_pkl, "wb") as f:
        pickle.dump(stats, f)
    print(f"  [{os.path.basename(out_pkl)}] Done: {total_unique:,} unique, "
          f"{total_weighted:,} weighted", flush=True)


if __name__ == "__main__":
    main()
