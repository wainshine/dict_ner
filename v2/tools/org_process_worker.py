#!/usr/bin/env python3
"""Per-chunk org recognition worker — reads chunk lines, writes JSONL results."""
import os, sys, json, time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from v2.org_recognizer import OrgDPRecognizer
from core.types import SegType

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <chunk.csv> <output.jsonl> <version>")
        sys.exit(1)

    inp, out_path, version = sys.argv[1], sys.argv[2], sys.argv[3]

    rec = OrgDPRecognizer(os.path.join(BASE, "data"), version=version)
    t0 = time.time()
    total = 0
    seg_dist = Counter()

    with open(inp, encoding="utf-8") as fin, open(out_path, "w", encoding="utf-8") as fout:
        for line in fin:
            text = line.strip()
            if not text or len(text) < 2:
                continue
            res = rec.recognize(text)
            seg_dist[len(res.segments)] += 1
            record = {
                "original": text,
                "segments": [
                    {"text": s.text, "type": s.seg_type.value, "poi_type": s.poi_type}
                    for s in res.segments
                ],
            }
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            total += 1
            if total % 500000 == 0:
                print(f"  [{os.path.basename(inp)}] {total//10000:>4}w in {time.time()-t0:.0f}s", flush=True)

    elapsed = time.time() - t0
    stats = {"total": total, "seg_dist": dict(seg_dist.most_common()), "elapsed": elapsed}
    stats_path = out_path.replace(".jsonl", "_stats.json")
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False)
    print(f"  [{os.path.basename(out_path)}] Done: {total:,} records in {elapsed:.0f}s ({total/elapsed:.0f} rec/s)", flush=True)


if __name__ == "__main__":
    main()
