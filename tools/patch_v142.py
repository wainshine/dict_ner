#!/usr/bin/env python3
"""v1.4.2 词典补丁 — F5 村/居委会复合词清除 + F6 d3 低频清理

F5: d1 词条以 村民委员会/居民委员会/村委会/居委会 结尾 → 从 d1 删除
    (正确切分: XX村 VILLAGE + 委员会 d4)
    注意: 当前实现未校验前缀是否为已知村名 (docstring 旧描述与代码不符,
    见审计 Batch 2; 现役 v1.5.0 词典已按当前行为固化)
F6: d3 freq<10 删除
输入: dicts/org_v1.4.1.pkl → 输出: dicts/org_v1.4.2.pkl + export CSV 更新
"""
import csv
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.pipeline_base import atomic_pickle_dump

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_DIR = os.path.join(BASE, "dicts")
DATA = os.path.join(BASE, "data")
EXPORT_DIR = os.path.join(DICT_DIR, "export")

COMMITTEE_SUFFIXES = ("村民委员会", "居民委员会", "村委会", "居委会")
D3_FREQ_MIN = 10


def load_villages():
    villages = set()
    path = os.path.join(DATA, "areas", "villages.csv")
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = row.get("name", "").strip().strip('"')
            if name:
                villages.add(name)
    return villages


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--src-v", default="v1.4.1")
    ap.add_argument("--dst-v", default="v1.4.2")
    v = ap.parse_args()
    src = os.path.join(DICT_DIR, f"org_{v.src_v}.pkl")
    dst = os.path.join(DICT_DIR, f"org_{v.dst_v}.pkl")
    with open(src, "rb") as f:
        dd = pickle.load(f)
    d1 = dict(dd["d1_freqs"])
    d3 = dict(dd["d3_freqs"])
    d4 = dict(dd["d4_freqs"])

    villages = load_villages()
    # 当前仅用于日志; 删除决策未使用该集合 (审计项, Batch 2 处理)
    print(f"areas villages: {len(villages):,}")

    removed = []
    for w in list(d1.keys()):
        for sfx in COMMITTEE_SUFFIXES:
            if w.endswith(sfx) and len(w) > len(sfx):
                removed.append((w, d1.pop(w), sfx))
                break
    print(f"F5: 删除 {len(removed)} 条复合词")
    for w, f, sfx in sorted(removed, key=lambda x: -x[1])[:8]:
        print(f"  {w} ({f:,}) -> {w[:-len(sfx)]} + {sfx}")

    d3_removed = [(w, d3.pop(w)) for w, f in list(d3.items()) if f < D3_FREQ_MIN]
    print(f"F6: d3 freq<{D3_FREQ_MIN} 删除 {len(d3_removed)} 条")

    out = {"d1_freqs": d1, "d3_freqs": d3, "d4_freqs": d4}
    atomic_pickle_dump(out, dst)
    print(f"saved: {dst} ({os.path.getsize(dst)/1024/1024:.1f}MB)")
    print(f"d1: {len(dd['d1_freqs']):,} → {len(d1):,}  d3: {len(dd['d3_freqs']):,} → {len(d3):,}")

    for key, fname in (("d1_freqs", "d1"), ("d3_freqs", "d3"), ("d4_freqs", "d4")):
        path = os.path.join(EXPORT_DIR, f"org_{fname}_export.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["word", "freq"])
            for word, freq in sorted(out[key].items(), key=lambda x: -x[1]):
                w.writerow([word, freq])
    print(f"export CSV updated: {EXPORT_DIR}/org_*_v1.4.2.csv")


if __name__ == "__main__":
    main()
