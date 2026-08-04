#!/usr/bin/env python3
"""v1.3.0 eval 重切 worker — v3 引擎识别 chunk, 产出与 legacy eval 同构的 JSONL+stats

用法: python v3/eval_cut_worker.py <org|poi|loc> <chunk_csv> <out_jsonl> <out_stats_json>
"""
import csv
import json
import os
import sys
import time
from collections import Counter

csv.field_size_limit(sys.maxsize)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")


def build_engine(system, version="v1.3.0"):
    from v3.engine.configs import build_org_engine, build_poi_engine, build_loc_engine
    if system == "org":
        return build_org_engine(version)
    if system == "poi":
        return build_poi_engine(f"poi_{version}.pkl")
    return build_loc_engine(f"loc_{version}")


def main():
    system, chunk_path, out_jsonl, out_stats = sys.argv[1:5]
    version = sys.argv[5] if len(sys.argv) > 5 else "v1.3.0"
    engine = build_engine(system, version)
    t0 = time.time()

    total = 0
    seg_dist = Counter()
    type_dist = Counter()
    seq_dist = Counter()
    with open(chunk_path, encoding="utf-8") as f, \
            open(out_jsonl, "w", encoding="utf-8") as out:
        if system == "poi":
            rows = (line.rstrip("\n").split("\t")[0].strip() for line in f)
        else:
            reader = csv.reader(f)
            first = next(reader, None)
            rest = (row[0] for row in reader if row)
            rows = rest if (first and first[0] == "dict") else (
                [first[0]] if first and first[0] else [])
            if first and first[0] and first[0] != "dict":
                import itertools
                rows = itertools.chain([first[0]], rest)
        for name in rows:
            if not name:
                continue
            res = engine.recognize(name)
            segs = res.segments
            total += 1
            seg_dist[len(segs)] += 1
            seq = " → ".join(s.seg_type.value for s in segs)
            seq_dist[seq] += 1
            seg_items = []
            for s in segs:
                type_dist[s.seg_type.value] += 1
                seg_items.append({"text": s.text, "type": s.seg_type.value,
                                  "poi_type": s.poi_type})
            out.write(json.dumps({"original": name, "segments": seg_items},
                                 ensure_ascii=False) + "\n")
            if total % 500000 == 0:
                print(f"[{os.path.basename(out_jsonl)}] {total:,}", flush=True)

    stats = {"total": total,
             "seg_dist": dict(seg_dist),
             "type_dist": dict(type_dist),
             "seq_dist": dict(seq_dist),
             "elapsed": time.time() - t0}
    with open(out_stats, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False)
    print(f"[{os.path.basename(out_jsonl)}] DONE total={total:,} "
          f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
