#!/usr/bin/env python3
"""D1 段级健康度基线 — 无金标指标: 后缀/行业/地址验证率 + 低频序列率

用法: python v3/seg_quality.py [--n 200000] [--chunk data/split/org/chunk_00.csv]
      [--engine org|poi] [--out output/v3_seg_baseline.json]
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter

csv.field_size_limit(sys.maxsize)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import SegType

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")

ADDR_SEG_TYPES = {SegType.PROVINCE, SegType.CITY, SegType.DISTRICT,
                  SegType.TOWN, SegType.VILLAGE, SegType.COMMUNITY, SegType.ROAD}


def load_sql_sets():
    sql_suffixes, trade, addr = set(), set(), set()
    with open(os.path.join(DATA, "suffix_segments_sql.csv"), encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            w = row["d4"].strip()
            if w:
                sql_suffixes.add(w)
    with open(os.path.join(DATA, "trade_segments_sql.csv"), encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            w = row["d3"].strip()
            if w:
                trade.add(w)
    with open(os.path.join(DATA, "addr_segments_sql.csv"), encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            w = row["d1"].strip()
            if w:
                addr.add(w)
    return sql_suffixes, trade, addr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200000)
    ap.add_argument("--chunk", default=os.path.join(DATA, "split", "org", "chunk_00.csv"))
    ap.add_argument("--engine", default="org", choices=["org", "poi"])
    ap.add_argument("--v3", action="store_true", help="使用 v3 统一引擎 (含R1修复)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.v3:
        from v3.pipeline import V3Pipeline
        pipe = V3Pipeline()
    else:
        from pipeline import DictNerPipeline
        pipe = DictNerPipeline()
    sql_suffixes, trade, addr = load_sql_sets()
    print(f"SQL sets: suffix={len(sql_suffixes):,} trade={len(trade):,} addr={len(addr):,}")

    names = []
    with open(args.chunk, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            names.append(row["dict"])
            if len(names) >= args.n:
                break
    print(f"sample: {len(names):,} names from {os.path.basename(args.chunk)}")

    n_done = 0
    seg_total = 0
    last_in_sql = 0
    last_present = 0
    ind_total = 0
    ind_in_trade = 0
    addr_total = 0
    addr_in_sql = 0
    overmerge_suspect = 0
    seq_counter = Counter()
    results = []

    for name in names:
        res = pipe._remap_org_segments(pipe.org.recognize(name))
        res.segments = pipe._merge_over_split(res.segments)
        segs = res.segments
        if not segs:
            continue
        n_done += 1
        seg_total += len(segs)
        seq = "→".join(s.seg_type.value for s in segs)
        seq_counter[seq] += 1
        results.append((name, segs))

        last = segs[-1]
        if last.seg_type == SegType.ORG_SUFFIX:
            last_present += 1
            if last.text in sql_suffixes:
                last_in_sql += 1
            hits = sum(1 for sfx in sql_suffixes if sfx != last.text and sfx in last.text)
            if hits >= 1 and last.text not in sql_suffixes:
                overmerge_suspect += 1

        for s in segs:
            if s.seg_type == SegType.INDUSTRY:
                ind_total += 1
                if s.text in trade:
                    ind_in_trade += 1
            elif s.seg_type in ADDR_SEG_TYPES:
                addr_total += 1
                if s.text in addr:
                    addr_in_sql += 1

    low_seq = sum(1 for _, segs in results
                  if seq_counter["→".join(s.seg_type.value for s in segs)] < 10)

    metrics = {
        "chunk": args.chunk, "n": n_done,
        "avg_segments": round(seg_total / max(1, n_done), 3),
        "last_seg_org_suffix_rate": round(last_present / max(1, n_done), 4),
        "suffix_verified_rate": round(last_in_sql / max(1, last_present), 4),
        "industry_verified_rate": round(ind_in_trade / max(1, ind_total), 4),
        "addr_verified_rate": round(addr_in_sql / max(1, addr_total), 4),
        "overmerge_suspect_rate": round(overmerge_suspect / max(1, n_done), 4),
        "low_freq_seq_rate": round(low_seq / max(1, n_done), 4),
        "counts": {
            "last_present": last_present, "last_in_sql": last_in_sql,
            "ind_total": ind_total, "ind_in_trade": ind_in_trade,
            "addr_total": addr_total, "addr_in_sql": addr_in_sql,
            "overmerge_suspect": overmerge_suspect, "low_seq": low_seq,
        },
    }
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        print(f"saved: {args.out}")


if __name__ == "__main__":
    main()
