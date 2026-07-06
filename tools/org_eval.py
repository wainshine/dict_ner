#!/usr/bin/env python3
"""机构名识别 Demo V2 — 含分支识别 + 校准品牌分"""

import os, sys, time, pickle, csv
from collections import Counter
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from org.recognizer import OrgDPRecognizer
from core.types import SegType

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_DIR = os.path.join(BASE, "dicts")
DATA_DIR = os.path.join(BASE, "data")


def load_samples():
    samp_path = os.path.join(DICT_DIR, "org_sample.pkl")
    if os.path.exists(samp_path):
        with open(samp_path, "rb") as f:
            return pickle.load(f)
    return []


def main():
    print("Loading OrgRecognizer V2...", flush=True)
    t0 = time.time()
    rec = OrgDPRecognizer(DICT_DIR, DATA_DIR)
    print(f"  Loaded in {time.time()-t0:.1f}s", flush=True)

    samples = load_samples()
    print(f"\nRecognizing {len(samples):,} org names...", flush=True)
    t0 = time.time()

    stats = {"d4_hit": 0, "d3_hit": 0, "d1_hit": 0, "branch_found": 0}
    d4_cats = Counter()
    brand_scores = []

    for text, idf in samples:
        res = rec.recognize(text)

        # d4: check if LAST segment ends with d444 suffix
        if res.segments:
            last = res.segments[-1]
            for sfx in rec.d4_suffixes:
                if last.text.endswith(sfx) and len(last.text) >= len(sfx):
                    stats["d4_hit"] += 1
                    if hasattr(last, 'poi_type') and last.poi_type:
                        d4_cats[last.poi_type] += 1
                    break

        # d3: check if any segment contains d333 word
        d3_found = False
        for s in res.segments:
            for word in rec.d3_words:
                if word in s.text:
                    d3_found = True
                    break
            if d3_found: break
        if d3_found: stats["d3_hit"] += 1

        # d1: check if V5 recognized any addr segments
        d1_found = False
        for s in res.segments:
            if s.seg_type not in (SegType.UNKNOWN, SegType.CHAR):
                d1_found = True
                break
        if d1_found: stats["d1_hit"] += 1

        # branch
        if any(m in text for m in ["分公司","子公司","分行","支行","分店","分厂"]):
            stats["branch_found"] += 1

        # Collect calibrated brand scores
        for s in res.segments:
            if len(s.text) >= 2 and s.confidence < 0.9:
                bs = rec.brand_score(s.text)
                brand_scores.append((s.text, bs))

    elapsed = time.time() - t0
    total = len(samples)
    print(f"  Done: {total:,} in {elapsed:.1f}s ({total/elapsed:.0f} rec/s)\n", flush=True)

    print("=== Coverage ===", flush=True)
    for k, v in stats.items():
        print(f"  {k}: {v} ({100*v/total:.1f}%)", flush=True)

    print(f"\n=== d4 Categories ===", flush=True)
    for cat, cnt in d4_cats.most_common(12):
        print(f"  {cat:20s}: {cnt:>6,}", flush=True)

    # Sample predictions with branch detection
    print(f"\n=== Examples (with branch markers) ===", flush=True)
    seen = set()
    for text, _ in samples:
        if any(m in text for m in ["分公司", "支行", "分行", "子公司"]):
            if text not in seen:
                seen.add(text)
                res = rec.recognize(text)
                segs = " | ".join(f"「{s.text}」" for s in res.segments)
                print(f"  [{len(res.segments)}seg] {segs}", flush=True)
        if len(seen) >= 8: break

    # Regular examples
    print(f"\n=== Regular Examples ===", flush=True)
    for text, _ in samples[:12]:
        res = rec.recognize(text)
        segs = " | ".join(f"「{s.text}」" for s in res.segments)
        print(f"  [{len(res.segments)}seg] {segs}", flush=True)

    # Brand scores
    print(f"\n=== Brand Scores (higher=more likely brand) ===", flush=True)
    brand_scores.sort(key=lambda x: -x[1])
    for text, score in brand_scores[:12]:
        print("  \"{text:20s}\"  score={score:.4f}  ✓ brand", flush=True)
    print("  ...", flush=True)
    brand_scores.sort(key=lambda x: x[1])
    for text, score in brand_scores[:12]:
        print("  \"{text:20s}\"  score={score:.4f}  ✗ non-brand", flush=True)


if __name__ == "__main__":
    main()
