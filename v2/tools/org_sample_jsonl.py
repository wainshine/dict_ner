#!/usr/bin/env python3
"""org16kw 10万条采样 → JSONL + 分析类型组合"""

import os, sys, time, json
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from v2.org_recognizer import OrgDPRecognizer
from core.types import SegType

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDR_TYPES = {SegType.PROVINCE, SegType.CITY, SegType.DISTRICT,
              SegType.TOWN, SegType.VILLAGE, SegType.COMMUNITY, SegType.ROAD}

def main():
    rec = OrgDPRecognizer(os.path.join(BASE, "dicts"), os.path.join(BASE, "data"))

    # Sample 100K from first 2 chunks
    samples = []
    with open(os.path.join(BASE, "data", "split/org", "chunk_00.csv"), encoding="utf-8") as f:
        next(f)
        for line in f:
            text = line.strip().rsplit(",", 5)[0].strip()
            if text and len(text) >= 4: samples.append(text)
            if len(samples) >= 100000: break

    print(f"Recognizing {len(samples):,} samples...", flush=True)
    t0 = time.time()
    type_patterns = Counter()
    all_results = []
    seg_total = 0

    for text in samples:
        res = rec.recognize(text)
        all_results.append(res)
        seg_total += len(res.segments)

        # Build type pattern
        pattern = []
        for s in res.segments:
            if s.seg_type in ADDR_TYPES: pattern.append("D1")
            elif s.seg_type == SegType.POI: pattern.append("D4")
            elif s.seg_type == SegType.LOCATION: pattern.append("D3")
            else: pattern.append("D2")
        type_patterns["+".join(pattern)] += 1

    elapsed = time.time() - t0
    print(f"  Done: {elapsed:.0f}s ({len(samples)/elapsed:.0f} rec/s)", flush=True)
    print(f"  Avg seg: {seg_total/len(samples):.1f}", flush=True)
    print()

    # Type patterns
    print("=== Type Combination Patterns ===", flush=True)
    for pat, cnt in type_patterns.most_common(25):
        pct = 100*cnt/len(samples)
        bar = "█" * int(pct/2)
        print(f"  {pat:40s}: {cnt:>8,} ({pct:5.1f}%) {bar}", flush=True)
    print()

    # Per-type stats
    d1_hit = d2_hit = d3_hit = d4_hit = 0
    for r in all_results:
        for s in r.segments:
            if s.seg_type in ADDR_TYPES: d1_hit += 1
            elif s.seg_type == SegType.POI: d4_hit += 1
            elif s.seg_type == SegType.LOCATION: d3_hit += 1
            else: d2_hit += 1
    print(f"d1={100*d1_hit/len(samples):.0f}%  d2={100*d2_hit/len(samples):.0f}%  d3={100*d3_hit/len(samples):.0f}%  d4={100*d4_hit/len(samples):.0f}%", flush=True)
    print()

    # Save JSONL for spot check
    out_path = os.path.join(BASE, "output", "org_sample_100k.jsonl")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for r in all_results:
            d = {"original": r.original, "segments": []}
            for s in r.segments:
                label = "D4" if s.seg_type == SegType.POI else \
                        "D3" if s.seg_type == SegType.LOCATION else \
                        "D1" if s.seg_type in ADDR_TYPES else "D2"
                d["segments"].append({"text": s.text, "type": s.seg_type.value,
                                      "layer": label, "poi_type": s.poi_type})
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    mb = os.path.getsize(out_path)/1024/1024
    print(f"Saved {len(samples):,} records to {out_path} ({mb:.1f}MB)", flush=True)

    print("Run: python3 -c \"import json,random; lines=[json.loads(l) for l in open('output/org_sample_100k.jsonl')]; random.shuffle(lines); [print(json.dumps(l,ensure_ascii=False)) for l in lines[:30]]\"", flush=True)

if __name__ == "__main__":
    main()
