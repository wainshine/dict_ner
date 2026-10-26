#!/usr/bin/env python3
"""v1.4.1 词典补丁 — F1 括号归一化 + F2 误杀复合后缀回补 + F3 数字垃圾清理 + F4 可读导出

输入: dicts/org_v1.4.0.pkl, dicts/poi_v1.4.0.pkl
输出: dicts/org_v1.4.1.pkl, dicts/poi_v1.4.1.pkl + dicts/export/*.csv
"""
import csv
import json
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.pipeline_base import atomic_pickle_dump

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_DIR = os.path.join(BASE, "dicts")
DATA = os.path.join(BASE, "data")
EXPORT_DIR = os.path.join(DICT_DIR, "export")

BRACKET_CHARS = "()（）[]【】"
RESCUE_MIN_ORG = 5000
RESCUE_MAX_RATIO = 15.0
RESCUE_FREQ_CAP = 50000
RESCUE_FREQ_FLOOR = 50000


def strip_brackets(w):
    return w.translate(str.maketrans("", "", BRACKET_CHARS)).strip()


def f1_bracket_merge(d4):
    moved = 0
    for w in list(d4.keys()):
        if any(c in w for c in BRACKET_CHARS):
            cleaned = strip_brackets(w)
            if not cleaned:
                del d4[w]
                moved += 1
                continue
            d4[cleaned] = d4.get(cleaned, 0) + d4.pop(w)
            moved += 1
    return d4, moved


def f2_rescue(d4):
    candidates = []
    with open(os.path.join(DATA, "suffix_segments_sql.csv"), encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            w = row["d4"].strip()
            if not w or len(w) < 2 or w in d4:
                continue
            try:
                org = int(row.get("org", 0) or 0)
                loc = int(row.get("loc", 0) or 0)
            except ValueError:
                continue
            if loc <= org:
                continue
            if org < RESCUE_MIN_ORG or loc >= RESCUE_MAX_RATIO * max(1, org):
                continue
            candidates.append((w, org))
    for w, org in candidates:
        d4[w] = min(max(org, RESCUE_FREQ_FLOOR), RESCUE_FREQ_CAP)
    return d4, candidates


F3_KEEP = {"4S店", "2元店", "1号店"}


def f2b_d1_conflict_clean(d1, rescued):
    from v3.engine.configs import _d1_type_infer, _build_bare_name_table
    bt = _build_bare_name_table()
    removed = []
    for w, _ in rescued:
        if w in d1:
            st = _d1_type_infer(w, bt)
            from core.types import SegType
            if st in (SegType.TOWN, SegType.VILLAGE, SegType.CITY, SegType.DISTRICT):
                removed.append((w, d1.pop(w), st.value))
    return d1, removed


def f3_digit_clean(d4):
    removed = []
    for w in list(d4.keys()):
        if any(c.isdigit() for c in w) and w not in F3_KEEP:
            removed.append((w, d4.pop(w)))
    return d4, removed


def export_csv(name, dicts_map):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    for key, fname in (("d1_freqs", "d1"), ("d3_freqs", "d3"), ("d4_freqs", "d4")):
        path = os.path.join(EXPORT_DIR, f"{name}_{fname}_export.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["word", "freq"])
            for word, freq in sorted(dicts_map[key].items(), key=lambda x: -x[1]):
                w.writerow([word, freq])
        print(f"  exported {path} ({len(dicts_map[key]):,})")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--src-v", default="v1.4.0")
    ap.add_argument("--dst-v", default="v1.4.1")
    v = ap.parse_args()
    for sysname in ("org", "poi"):
        src = os.path.join(DICT_DIR, f"{sysname}_{v.src_v}.pkl")
        dst = os.path.join(DICT_DIR, f"{sysname}_{v.dst_v}.pkl")
        with open(src, "rb") as f:
            dd = pickle.load(f)
        d4 = dict(dd["d4_freqs"])

        d1 = dict(dd["d1_freqs"])
        d4, n1 = f1_bracket_merge(d4)
        d4, rescued = f2_rescue(d4)
        d4, removed = f3_digit_clean(d4)
        d1, d1_removed = f2b_d1_conflict_clean(d1, rescued)

        print(f"== {sysname} {v.src_v} → {v.dst_v} ==")
        print(f"  F1 括号归一化: {n1} 条合并")
        print(f"  F2 复合后缀回补: {len(rescued)} 条 "
              f"{[w for w, _ in rescued[:12]]}")
        print(f"  F2b d1冲突清理: {len(d1_removed)} 条 {d1_removed}")
        print(f"  F3 数字垃圾: {len(removed)} 条 {[w for w, _ in removed]}")
        print(f"  d4: {len(dd['d4_freqs']):,} → {len(d4):,}")

        out = {"d1_freqs": d1, "d3_freqs": dd["d3_freqs"], "d4_freqs": d4}
        atomic_pickle_dump(out, dst)
        print(f"  saved: {dst} ({os.path.getsize(dst)/1024/1024:.1f}MB)")
        export_csv(sysname, out)

    log_path = os.path.join(DICT_DIR, f"{v.dst_v}_patch_log.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump({"src": v.src_v, "dst": v.dst_v,
                   "f1": "bracket merge", "f2_rescue": True,
                   "f3": "digit clean"}, f)


if __name__ == "__main__":
    main()
