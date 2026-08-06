#!/usr/bin/env python3
"""结构 badcase 提取 — seq 全池单例 / 段数≥13 的训练行 (Q2 时间盒实验)

输入: output/v3_feat/final_train6.csv (特征已含, 只过滤行)
产出:
  output/v4_train_badcase.csv   命中行 (text,label,seq,n_segs) 永久保留
  output/v3_feat/final_train9.csv  过滤后训练集

用法: python3 v3/struct_badcase.py [--max-segs 13]
"""
import argparse
import csv
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

csv.field_size_limit(sys.maxsize)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "output", "v3_feat", "final_train6.csv")
DST = os.path.join(BASE, "output", "v3_feat", "final_train9.csv")
BADCASE = os.path.join(BASE, "output", "v4_train_badcase.csv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-segs", type=int, default=13)
    args = ap.parse_args()

    from v3.engine.configs import build_org_engine
    eng = build_org_engine("v1.5.0")

    rows = []
    seqs = []
    with open(SRC, encoding="utf-8") as f:
        for i, r in enumerate(csv.DictReader(f)):
            rows.append(r)
            res = eng.recognize(r["text"])
            seqs.append(" ".join(s.seg_type.value for s in res.segments))
            if (i + 1) % 500000 == 0:
                print(f"  seq {i+1:,}", flush=True)

    seq_count = Counter(seqs)
    bad_idx = set()
    for i, (r, seq) in enumerate(zip(rows, seqs)):
        n_segs = len(seq.split()) if seq else 0
        if seq_count[seq] == 1 or n_segs >= args.max_segs:
            bad_idx.add(i)

    with open(BADCASE, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["text", "label", "source", "seq", "n_segs"])
        for i in sorted(bad_idx):
            w.writerow([rows[i]["text"], rows[i]["label"],
                        rows[i].get("source", ""), seqs[i],
                        len(seqs[i].split())])

    with open(DST, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for i, r in enumerate(rows):
            if i not in bad_idx:
                w.writerow(r)

    print(f"total {len(rows):,} → badcase {len(bad_idx):,} "
          f"({100*len(bad_idx)/len(rows):.2f}%), train9 {len(rows)-len(bad_idx):,}")
    print(f"badcase: {BADCASE}")
    print(f"train9:  {DST}")


if __name__ == "__main__":
    main()
