#!/usr/bin/env python3
"""E2.1 seq_dist 对比 — v1.2.3 vs v1.3.0 全量序列分布对比

用法: python v3/seq_dist_compare.py
产出: output/v1.3.0_seq_compare.md
"""
import glob
import json
import os
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "output")


def load_seq_stats(system, version):
    total = 0
    seq = Counter()
    type_dist = Counter()
    seg_dist = Counter()
    for fp in glob.glob(os.path.join(OUT, f"{system}_eval", f"{system}_{version}",
                                     "chunk_*_stats.json")):
        with open(fp, encoding="utf-8") as f:
            d = json.load(f)
        total += d["total"]
        seq.update(d.get("seq_dist", {}))
        type_dist.update(d.get("type_dist", {}))
        seg_dist.update({int(k): v for k, v in d.get("seg_dist", {}).items()})
    return {"total": total, "seq": seq, "type": type_dist, "seg": seg_dist}


def low_freq_stats(seq_counter, threshold=10):
    kinds = sum(1 for c in seq_counter.values() if c < threshold)
    records = sum(c for c in seq_counter.values() if c < threshold)
    return kinds, records


def main():
    lines = ["# v1.2.3 vs v1.3.0 seq_dist 全量对比", ""]
    for system in ("org", "poi", "loc"):
        old = load_seq_stats(system, "v1.2.3")
        new = load_seq_stats(system, "v1.3.0")
        if not old["total"] or not new["total"]:
            continue
        ok, orc = low_freq_stats(old["seq"])
        nk, nrc = low_freq_stats(new["seq"])
        lines += [f"## {system.upper()} ({old['total']:,} 条)", "",
                  "| 指标 | v1.2.3 | v1.3.0 | Δ |",
                  "|------|-------:|-------:|---:|",
                  f"| 序列种类 | {len(old['seq']):,} | {len(new['seq']):,} | {len(new['seq'])-len(old['seq']):+,} |",
                  f"| 低频序列种类 (<10) | {ok:,} | {nk:,} | {nk-ok:+,} |",
                  f"| 低频序列覆盖记录 | {orc:,} ({100*orc/old['total']:.2f}%) | {nrc:,} ({100*nrc/new['total']:.2f}%) | {nrc-orc:+,} |",
                  ""]
        common = set(old["seq"]) & set(new["seq"])
        only_old = set(old["seq"]) - set(new["seq"])
        only_new = set(new["seq"]) - set(old["seq"])
        lines += [f"- 共有序列 {len(common):,} | 仅旧版 {len(only_old):,} | 仅新版 {len(only_new):,}",
                  "", "### 旧版有而新版消失的高频序列 top10 (修复证据)", "",
                  "| 序列 | 旧freq |", "|------|-----:|"]
        gone = sorted(only_old, key=lambda s: -old["seq"][s])[:10]
        for s in gone:
            lines.append(f"| {s} | {old['seq'][s]:,} |")
        lines += ["", "### 新版新增的高频序列 top10", "",
                  "| 序列 | 新freq |", "|------|-----:|"]
        born = sorted(only_new, key=lambda s: -new["seq"][s])[:10]
        for s in born:
            lines.append(f"| {s} | {new['seq'][s]:,} |")
        lines += ["", "### 类型分布变化", "",
                  "| 类型 | v1.2.3 | v1.3.0 | Δ |", "|------|-------:|-------:|---:|"]
        for t in sorted(set(old["type"]) | set(new["type"])):
            o, n = old["type"].get(t, 0), new["type"].get(t, 0)
            lines.append(f"| {t} | {o:,} | {n:,} | {n-o:+,} |")
        lines.append("")

    path = os.path.join(OUT, "v1.3.0_seq_compare.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))
    print(f"\nreport: {path}")


if __name__ == "__main__":
    main()
