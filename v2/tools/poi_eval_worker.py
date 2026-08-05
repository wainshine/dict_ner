#!/usr/bin/env python3
"""Per-chunk POI recognition worker for split/poi TSV format."""
import os, sys, json, time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from v2.poi_recognizer import PoiRecognizer

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    inp, out_path, version = sys.argv[1], sys.argv[2], sys.argv[3]
    dict_name = f"poi_{version}.pkl"
    rec = PoiRecognizer(os.path.join(BASE, "data"), dict_name=dict_name)
    t0 = time.time()
    total = 0
    seg_dist = Counter()
    type_dist = Counter()
    seq_dist = Counter()

    with open(inp, encoding="utf-8") as fin, open(out_path, "w", encoding="utf-8") as fout:
        for line in fin:
            text = line.strip().split("\t")[0].strip()
            if not text or len(text) < 2:
                continue
            res = rec.recognize(text)
            seg_dist[len(res.segments)] += 1
            type_seq = " → ".join(s.seg_type.value for s in res.segments)
            seq_dist[type_seq] += 1
            for s in res.segments:
                type_dist[s.seg_type.value] += 1
            record = {
                "original": text,
                "segments": [
                    {"text": s.text, "type": s.seg_type.value, "poi_type": s.poi_type}
                    for s in res.segments
                ],
            }
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            total += 1
            if total % 2000000 == 0:
                print(f"  [{os.path.basename(inp)}] {total//10000:>4}w in {time.time()-t0:.0f}s", flush=True)

    elapsed = time.time() - t0
    stats = {
        "total": total, "seg_dist": dict(seg_dist.most_common()),
        "type_dist": dict(type_dist.most_common()), "seq_dist": dict(seq_dist.most_common()),
        "elapsed": elapsed,
    }
    stats_path = out_path.replace(".jsonl", "_stats.json")
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False)
    print(f"  [{os.path.basename(out_path)}] Done: {total:,} records in {elapsed:.0f}s ({total/elapsed:.0f} rec/s)", flush=True)


if __name__ == "__main__":
    main()
