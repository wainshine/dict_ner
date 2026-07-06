#!/usr/bin/env python3
"""Per-chunk POI stats — DP version, d1/d2/d3/d4 freq collection"""
import os, sys, re, pickle
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from org.recognizer import OrgDPRecognizer
from core.types import SegType

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDR_TYPES = {SegType.PROVINCE, SegType.CITY, SegType.DISTRICT,
              SegType.TOWN, SegType.VILLAGE, SegType.COMMUNITY, SegType.ROAD}


def clean_d2(text: str) -> str:
    for ch in '()（）[]【】{}':
        text = text.replace(ch, '')
    return text.strip()


def is_good_d2(text: str) -> bool:
    if not text or len(text) < 2:
        return False
    if text.isascii() and not any('\u4e00' <= c <= '\u9fff' for c in text):
        return False
    # 复合 POI 碎片: XX路与/街与/道与/巷与
    if re.match(r'.*[路街巷道]与$', text):
        return False
    # 地址延伸: X号楼
    if text.endswith('号楼'):
        return False
    # 方位词
    if text in ('交叉口', '交汇处', '十字路口', '丁字路口', '交叉路口', '三岔路口'):
        return False
    # 国家名
    if text == '中国':
        return False
    # 建筑物编号: X栋/幢/座 (含数字字母)  + 纯数字栋
    if re.match(r'.*[0-9A-Za-z][栋幢座]$', text):
        return False
    # 时间描述: X小时 / 昼夜/通宵/全天/夜间
    if text.endswith('小时') or text in ('昼夜', '通宵', '全天', '夜间'):
        return False
    # 政治前缀
    if text in ('中共', '党委', '党组', '总支', '支部', '纪委', '人大', '政协'):
        return False
    # 第N序数
    if re.match(r'^第[一二三四五六七八九十百千万]+$', text):
        return False
    # 梯类设施
    if text.endswith('梯') and len(text) <= 4:
        return False
    # 字母数字区: A区/B区/1区/2区
    if re.match(r'^[A-Za-z0-9]+区$', text):
        return False
    # 数字店: 1店/2店
    if re.match(r'^[0-9]+店$', text):
        return False
    # 层数: B1层/2层/3层
    if re.match(r'^[0-9A-Za-z]+层$', text):
        return False
    return True


def process_line(rec, text, weight, d1_freqs, d2_freqs, d3_freqs, d4_freqs, d4_cats, seg_dist):
    res = rec.recognize(text)
    seg_dist[len(res.segments)] += weight

    d2_hit = d3_hit = d4_hit = 0
    for s in res.segments:
        if s.seg_type in ADDR_TYPES:
            d1_freqs[s.text] += weight
        elif s.seg_type == SegType.POI:
            d4_hit += weight
            d4_freqs[s.text] += weight
            if s.poi_type:
                d4_cats[s.poi_type] += weight
        elif s.text in rec.d3_set:
            d3_hit += weight
            d3_freqs[s.text] += weight
        elif s.seg_type == SegType.UNKNOWN:
            cleaned = clean_d2(s.text)
            if is_good_d2(cleaned):
                d2_hit += weight
                d2_freqs[cleaned] += weight

    return d2_hit, d3_hit, d4_hit


def main():
    inp, out_pkl = sys.argv[1], sys.argv[2]
    version = sys.argv[3] if len(sys.argv) > 3 else "poi_v1.1.0"
    seed_path = os.path.join(BASE, "dicts", "suffix_seed.csv")
    rec = OrgDPRecognizer(os.path.join(BASE, "data"),
                          dict_name="poi_v1.1.0.pkl",
                          disable_short_d4_penalty=True, allow_adjacent_d4=True,
                          poi_seed_path=seed_path)

    d1_freqs = Counter()
    d2_freqs = Counter()
    d3_freqs = Counter()
    d4_freqs = Counter()
    d4_cats = Counter()
    seg_dist = Counter()
    d2_hit_total = d3_hit_total = d4_hit_total = 0
    total_unique = 0
    total_weighted = 0

    basename = os.path.basename(inp)
    with open(inp, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.rsplit('\t', 1)
            if len(parts) == 2:
                text = parts[0]
                weight = int(parts[1])
            else:
                text = line
                weight = 1
            if not text or len(text) < 2:
                continue
            total_unique += 1
            total_weighted += weight
            h2, h3, h4 = process_line(rec, text, weight, d1_freqs, d2_freqs, d3_freqs, d4_freqs, d4_cats, seg_dist)
            d2_hit_total += h2; d3_hit_total += h3; d4_hit_total += h4

            if total_unique % 1000000 == 0:
                print(f"  [{basename}] {total_unique//10000}w  d2={len(d2_freqs):,} d3={len(d3_freqs):,} d4={len(d4_freqs):,}", flush=True)

    stats = {
        "total": total_weighted,
        "total_unique": total_unique,
        "d1_freqs": d1_freqs, "d2_freqs": d2_freqs,
        "d2_hit": d2_hit_total, "d3_hit": d3_hit_total, "d4_hit": d4_hit_total,
        "d3_freqs": d3_freqs, "d4_freqs": d4_freqs, "d4_cats": d4_cats,
        "seg_dist": seg_dist,
    }
    with open(out_pkl, "wb") as f:
        pickle.dump(stats, f)
    print(f"  [{os.path.basename(out_pkl)}] Done: {total_unique:,} unique, {total_weighted:,} weighted",
          flush=True)


if __name__ == "__main__":
    main()
