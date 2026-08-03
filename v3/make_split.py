#!/usr/bin/env python3
"""eval_set.csv → train/val/test 60/20/20 分层切分 (种子42, 持久化)

用法: python v3/make_split.py
产出: data/eval_split_{train,val,test}.csv
"""
import csv
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LABELS = ("ORG", "POI", "ADDR", "UNKNOWN")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")


def load_eval_set(path):
    rows = []
    skipped = 0
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            text = (row.get("text") or "").strip()
            label = (row.get("label") or "").strip()
            source = (row.get("source") or "").strip()
            if not text or label not in LABELS:
                skipped += 1
                continue
            rows.append((text, label, source))
    return rows, skipped


def main():
    from sklearn.model_selection import train_test_split

    src = os.path.join(DATA, "eval_set.csv")
    rows, skipped = load_eval_set(src)
    texts = [r[0] for r in rows]
    labels = [r[1] for r in rows]
    sources = [r[2] for r in rows]
    print(f"Loaded {len(rows):,} rows (skipped {skipped} malformed)")
    print("Label dist:", dict(Counter(labels)))

    idx = list(range(len(rows)))
    idx_train, idx_tmp = train_test_split(
        idx, test_size=0.4, random_state=42, stratify=labels)
    tmp_labels = [labels[i] for i in idx_tmp]
    idx_val, idx_test = train_test_split(
        idx_tmp, test_size=0.5, random_state=42, stratify=tmp_labels)

    for name, part in (("train", idx_train), ("val", idx_val), ("test", idx_test)):
        out = os.path.join(DATA, f"eval_split_{name}.csv")
        with open(out, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["text", "label", "source"])
            for i in part:
                w.writerow([texts[i], labels[i], sources[i]])
        dist = Counter(labels[i] for i in part)
        print(f"  {name}: {len(part):,} -> {out}  {dict(dist)}")


if __name__ == "__main__":
    main()
