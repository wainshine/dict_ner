#!/usr/bin/env python3
"""特征预计算 worker — 读一个 chunk CSV (text,label,source), 写特征 CSV

用法: python v3/precompute_worker.py <in_csv> <out_csv>
输出列: text,label,source,<FEATURE_NAMES...>
"""
import csv
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from v3.features import FeatureExtractor, FEATURE_NAMES

LABELS = ("ORG", "POI", "ADDR", "UNKNOWN")


def main():
    in_path, out_path = sys.argv[1], sys.argv[2]
    ex = FeatureExtractor()
    t0 = time.time()
    n = 0
    bad = 0
    with open(in_path, encoding="utf-8") as fin, \
            open(out_path, "w", encoding="utf-8", newline="") as fout:
        w = csv.writer(fout)
        w.writerow(["text", "label", "source", "type_orig"] + FEATURE_NAMES)
        for row in csv.DictReader(fin):
            text = (row.get("text") or "").strip()
            label = (row.get("label") or "").strip()
            if not text or (label and label not in LABELS):
                bad += 1
                continue
            try:
                vec = ex.extract_vector(text)
            except Exception:
                bad += 1
                continue
            w.writerow([text, label, row.get("source", ""),
                        row.get("type_orig", "")] + vec)
            n += 1
            if n % 2000 == 0:
                rate = n / (time.time() - t0)
                print(f"[{os.path.basename(out_path)}] {n:,} rows, {rate:.0f}/s", flush=True)
    print(f"[{os.path.basename(out_path)}] DONE {n:,} rows, {bad} skipped, "
          f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
