#!/usr/bin/env python3
"""E2.2 badcase 修复率 — v1.2.3 (legacy) vs v1.3.0 (v3引擎)

用法: python v3/badcase_eval.py --system org [--n 100000]
分类: REPAIRED(旧freq<10,新freq>=10) / STILL_LOW / CHANGED_LOW / UNCHANGED / NEW_LOW_OK
"""
import argparse
import csv
import glob
import json
import os
import sys
from collections import Counter

csv.field_size_limit(sys.maxsize)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "output")


def load_seq_freqs(system, version):
    seqs = Counter()
    for fp in glob.glob(os.path.join(OUT, f"{system}_eval", f"{system}_{version}",
                                     "chunk_*_stats.json")):
        with open(fp, encoding="utf-8") as f:
            seqs.update(json.load(f).get("seq_dist", {}))
    return seqs


def build_old(system, version="v1.2.3"):
    if version >= "v1.3.0":
        return build_new(system, version)
    if system == "org":
        from org.recognizer import OrgDPRecognizer
        return OrgDPRecognizer(DATA, version=version)
    if system == "poi":
        from poi.recognizer import PoiRecognizer
        return PoiRecognizer(DATA, dict_name=f"poi_{version}.pkl")
    from loc.builder import DictBuilder
    from loc.recognizer import AddressRecognizer
    b = DictBuilder.load(os.path.join(BASE, "dicts"), f"loc_{version}")
    return AddressRecognizer(b.dict_data)


def build_new(system, version="v1.3.0"):
    from v3.engine.configs import build_org_engine, build_poi_engine, build_loc_engine
    if system == "org":
        return build_org_engine(version)
    if system == "poi":
        return build_poi_engine(f"poi_{version}.pkl")
    return build_loc_engine(f"loc_{version}")


def seq_of(rec, text):
    return " → ".join(s.seg_type.value for s in rec.recognize(text).segments)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", required=True, choices=["org", "poi", "loc"])
    ap.add_argument("--n", type=int, default=100000)
    ap.add_argument("--old-v", default="v1.2.3")
    ap.add_argument("--new-v", default="v1.3.0")
    ap.add_argument("--badcase", default=None)
    args = ap.parse_args()

    badcase = args.badcase or os.path.join(
        DATA, f"badcase_{args.system}_v1.2.2.csv")
    texts = []
    with open(badcase, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            texts.append(row["text"])
            if len(texts) >= args.n:
                break
    print(f"badcase: {len(texts):,} from {os.path.basename(badcase)}")

    old_seqs = load_seq_freqs(args.system, args.old_v)
    new_seqs = load_seq_freqs(args.system, args.new_v)
    print(f"seq stats: v1.2.3 {len(old_seqs):,} kinds, v1.3.0 {len(new_seqs):,} kinds")

    old = build_old(args.system, args.old_v)
    new = build_new(args.system, args.new_v)

    cat = Counter()
    transitions = Counter()
    for i, t in enumerate(texts):
        so = seq_of(old, t)
        sn = seq_of(new, t)
        fo = old_seqs.get(so, 0)
        fn = new_seqs.get(sn, 0)
        if so == sn:
            cat["UNCHANGED"] += 1
        elif fn >= 10 > fo:
            cat["REPAIRED"] += 1
            transitions[(so, sn)] += 1
        elif fn < 10:
            cat["CHANGED_LOW"] += 1
        else:
            cat["OTHER"] += 1
        if (i + 1) % 20000 == 0:
            print(f"  {i+1:,}...", flush=True)

    total = len(texts)
    rep = cat["REPAIRED"]
    lines = [f"## {args.system.upper()} badcase 修复率 ({args.old_v}→{args.new_v})", "",
             f"- badcase: {total:,} (来自 {os.path.basename(badcase)})",
             f"- **REPAIRED: {rep:,} ({100*rep/total:.1f}%)**",
             f"- UNCHANGED: {cat['UNCHANGED']:,} ({100*cat['UNCHANGED']/total:.1f}%)",
             f"- CHANGED_LOW: {cat['CHANGED_LOW']:,} ({100*cat['CHANGED_LOW']/total:.1f}%)",
             f"- OTHER: {cat['OTHER']:,}", "",
             "### top 被修复的序列跃迁", "",
             "| 旧序列 | 新序列 | 数量 |", "|------|------|-----:|"]
    for (so, sn), c in transitions.most_common(15):
        lines.append(f"| {so} | {sn} | {c} |")
    out_md = os.path.join(OUT, f"{args.new_v}_badcase_{args.system}.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines[:12]))
    print(f"\nreport: {out_md}")


if __name__ == "__main__":
    main()
