#!/usr/bin/env python3
"""纯净集评测 worker — 抽样识别, 输出类别分布+误判样例

用法: python v3/pure_eval_worker.py <org_pure|poi_pure> <chunk_csv> <n> <out_json>
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LABELS = ("ORG", "POI", "ADDR", "UNKNOWN")
BATCH = 500


def load_names(system, chunk_path, n):
    from collections import deque
    buf = deque(maxlen=n)
    total = 0
    with open(chunk_path, encoding="utf-8") as f:
        for line in f:
            if system == "poi_pure":
                name = line.rstrip("\n").split("\t")[0].strip()
            else:
                name = line.strip().rsplit(",", 1)[0].strip() if "," in line else line.strip()
            if not name or len(name) < 2:
                continue
            total += 1
            if len(buf) < n:
                buf.append(name)
            else:
                j = np.random.randint(0, total)
                if j < n:
                    buf[j] = name
    return list(buf), total


def main():
    system, chunk_path, n, out_path = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
    np.random.seed(42)

    from v3.infer import V3Classifier
    clf = V3Classifier()

    names, total = load_names(system, chunk_path, n)
    counts = {lb: 0 for lb in LABELS}
    conf_sum = {lb: 0.0 for lb in LABELS}
    conf_n = {lb: 0 for lb in LABELS}
    expected = "ORG" if system == "org_pure" else "POI"
    wrong_examples = []

    for i in range(0, len(names), BATCH):
        batch = names[i:i + BATCH]
        results = clf.classify_batch(batch)
        for name, r in zip(batch, results):
            cat = r["category"]
            counts[cat] += 1
            conf_sum[cat] += r["confidence"]
            conf_n[cat] += 1
            if cat != expected and len(wrong_examples) < 200:
                wrong_examples.append([name, cat, round(r["confidence"], 3)])

    out = {
        "system": system, "chunk": os.path.basename(chunk_path),
        "corpus_total": total, "sampled": len(names),
        "counts": counts,
        "avg_conf": {lb: round(conf_sum[lb] / max(1, conf_n[lb]), 4) for lb in LABELS},
        "wrong_examples": wrong_examples,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"[{os.path.basename(out_path)}] DONE n={len(names):,} "
          f"{counts}", flush=True)


if __name__ == "__main__":
    main()
