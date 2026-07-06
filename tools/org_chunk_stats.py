#!/usr/bin/env python3
"""Per-chunk org stats — DP version, d1/d2/d3/d4 freq collection"""
import os, sys, pickle, csv as csv_mod
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from org.recognizer import OrgDPRecognizer
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
    """Filter out noise: single chars, punctuation, all-ascii, all-digit."""
    if not text or len(text) < 2:
        return False
    if text.isascii() and not any('\u4e00' <= c <= '\u9fff' for c in text):
        return False
    return True


def process_line(rec, text, d1_freqs, d2_freqs, d3_freqs, d4_freqs, d4_cats, seg_dist):
    res = rec.recognize(text)
    seg_dist[len(res.segments)] += 1

    d2_hit = d3_hit = d4_hit = 0
    for s in res.segments:
        if s.seg_type in ADDR_TYPES:
            d1_freqs[s.text] += 1
        elif s.seg_type == SegType.POI:
            d4_hit += 1
            d4_freqs[s.text] += 1
            if s.poi_type:
                d4_cats[s.poi_type] += 1
        elif s.text in rec.d3_set:
            d3_hit += 1
            d3_freqs[s.text] += 1
        elif s.seg_type in (SegType.UNKNOWN, SegType.BRAND):
            cleaned = clean_d2(s.text)
            if is_good_d2(cleaned):
                d2_hit += 1
                d2_freqs[cleaned] += 1

    return d2_hit, d3_hit, d4_hit


def main():
    inp, out_pkl = sys.argv[1], sys.argv[2]
    rec = OrgDPRecognizer(os.path.join(BASE_DIR, "dicts"), os.path.join(BASE_DIR, "data"))

    total = 0
    d1_freqs = Counter()
    d2_freqs = Counter()
    d3_freqs = Counter()
    d4_freqs = Counter()
    d4_cats = Counter()
    seg_dist = Counter()
    d2_hit_total = d3_hit_total = d4_hit_total = 0

    basename = os.path.basename(inp)
    with open(inp, encoding="utf-8") as f:
        first = f.readline()
        if first and not is_header(first.strip()):
            text = parse_text(first)
            if text and len(text) >= 4:
                total += 1
                h2, h3, h4 = process_line(rec, text, d1_freqs, d2_freqs, d3_freqs, d4_freqs, d4_cats, seg_dist)
                d2_hit_total += h2; d3_hit_total += h3; d4_hit_total += h4

        for line in f:
            text = parse_text(line)
            if not text or len(text) < 4:
                continue
            total += 1
            h2, h3, h4 = process_line(rec, text, d1_freqs, d2_freqs, d3_freqs, d4_freqs, d4_cats, seg_dist)
            d2_hit_total += h2; d3_hit_total += h3; d4_hit_total += h4

            if total % 2000000 == 0:
                print(f"  [{basename}] {total//10000}w  d2={len(d2_freqs):,} d3={len(d3_freqs):,} d4={len(d4_freqs):,}", flush=True)

    stats = {
        "total": total,
        "d1_freqs": d1_freqs, "d2_freqs": d2_freqs,
        "d2_hit": d2_hit_total, "d3_hit": d3_hit_total, "d4_hit": d4_hit_total,
        "d3_freqs": d3_freqs, "d4_freqs": d4_freqs, "d4_cats": d4_cats,
        "seg_dist": seg_dist,
    }
    with open(out_pkl, "wb") as f:
        pickle.dump(stats, f)
    print(f"  [{os.path.basename(out_pkl)}] Done: {total:,} records, d2={len(d2_freqs):,} unique", flush=True)


if __name__ == "__main__":
    main()
