#!/usr/bin/env python3
"""统计 org d4 中 d3+d4 可拆分后缀 — 只读，不改数据"""
import os, sys, pickle

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DICT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dicts")
SPLIT_SUFFIXES = {"厂", "店", "行", "部", "坊", "室", "所", "站", "场"}


def main():
    with open(os.path.join(DICT_DIR, "org_v1.2.1.pkl"), "rb") as f:
        org = pickle.load(f)
    d4_freqs = org["d4_freqs"]
    d3_freqs = org["d3_freqs"]

    polluted = []
    for d4_word, d4_freq in d4_freqs.items():
        if len(d4_word) < 3:
            continue
        for pos in range(len(d4_word) - 1, 0, -1):
            prefix = d4_word[:pos]
            suffix = d4_word[pos:]
            if suffix in SPLIT_SUFFIXES and prefix in d3_freqs:
                polluted.append((d4_word, d4_freq, prefix, d3_freqs[prefix], suffix))
                break

    print(f"d4 后缀总数: {len(d4_freqs):,}")
    print(f"d3 中可拆分: {len(polluted):,} ({100*len(polluted)/len(d4_freqs):.1f}%)")
    print()

    for threshold in [100, 500, 1000, 5000]:
        count = sum(1 for p in polluted if p[3] >= threshold)
        print(f"  d3 freq >= {threshold:>5}: {count:>5} d4 entries ({100*count/len(d4_freqs):.1f}%)")

    print(f"\nTop 30 (d3 freq >= 1000):")
    heavy = [p for p in polluted if p[3] >= 1000]
    heavy.sort(key=lambda x: -x[3])
    for d4w, d4f, prefix, d3f, sfx in heavy[:30]:
        print(f"  {d4w:12s}  d4_freq={d4f:>8,}  → d3({prefix}:{d3f:,}) + d4({sfx})")


if __name__ == "__main__":
    main()
