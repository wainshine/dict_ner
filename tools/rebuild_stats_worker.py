#!/usr/bin/env python3
"""Read JSONL → compute stats → write _stats.json"""
import os, sys, json
from collections import Counter

jpath = sys.argv[1]
spath = jpath.replace(".jsonl", "_stats.json")

total = 0
seg_dist = Counter()
type_dist = Counter()
seq_dist = Counter()

with open(jpath, encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        segs = r["segments"]
        seg_dist[len(segs)] += 1
        type_seq = " → ".join(s["type"] for s in segs)
        seq_dist[type_seq] += 1
        for s in segs:
            type_dist[s["type"]] += 1
        total += 1

stats = {
    "total": total, "seg_dist": dict(seg_dist.most_common()),
    "type_dist": dict(type_dist.most_common()), "seq_dist": dict(seq_dist.most_common()),
    "elapsed": 0,
}
with open(spath, "w", encoding="utf-8") as f:
    json.dump(stats, f, ensure_ascii=False)
print(f"  {os.path.basename(jpath)}: {total:,} records, {len(seq_dist):,} seqs", flush=True)
