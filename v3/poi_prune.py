#!/usr/bin/env python3
"""POI d1 位置证据剪枝 → dicts/poi_prune_v1.3.0.json

原理: poi 名称中 d1 词应出现在名称开头 (地址前缀)。
候选词 (poi d1 freq>=1000) 在 split/poi 语料中统计开头/结尾出现次数:
  - 结尾远多于开头 (end>=85%, end>=100):
      - 属 SQL 主导商业后缀 (org>=10000 且 org>=10*loc) → move: 移入 d4
      - 否则 → delete: 从 d1 删除 (品牌词)
用法: python v3/poi_prune.py [--chunks 4]
"""
import argparse
import csv
import json
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
DICT_DIR = os.path.join(BASE, "dicts")


def load_sql_dominant():
    result = set()
    with open(os.path.join(DATA, "suffix_segments_sql.csv"), encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            w = row["d4"].strip()
            if not w:
                continue
            try:
                org = int(row.get("org", 0) or 0)
                loc = int(row.get("loc", 0) or 0)
            except ValueError:
                continue
            if org >= 10000 and org >= 10 * max(1, loc):
                result.add(w)
    return result


def build_trie(words):
    trie = {}
    for w in words:
        node = trie
        for ch in w:
            node = node.setdefault(ch, {})
        node["#"] = w
    return trie


def prefix_hits(trie, text):
    node = trie
    for ch in text:
        if ch not in node:
            return None
        node = node[ch]
        if "#" in node:
            return node["#"]
    return node.get("#")


def suffix_hits(rtrie, text):
    node = rtrie
    for ch in reversed(text):
        if ch not in node:
            return None
        node = node[ch]
        if "#" in node:
            return node["#"]
    return node.get("#")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=4)
    ap.add_argument("--dict", default="poi_v1.2.3.pkl")
    ap.add_argument("--out", default=None)
    ap.add_argument("--min-freq", type=int, default=1000)
    ap.add_argument("--end-rate", type=float, default=0.85)
    ap.add_argument("--min-end", type=int, default=100)
    args = ap.parse_args()

    with open(os.path.join(DICT_DIR, args.dict), "rb") as f:
        poi = pickle.load(f)
    d1 = poi["d1_freqs"]
    d4 = poi["d4_freqs"]
    sql_dom = load_sql_dominant()
    print(f"poi d1={len(d1):,} d4={len(d4):,} sql_dominant={len(sql_dom):,}")

    from v3.engine.configs import _build_bare_name_table, _d1_type_infer
    from core.types import SegType
    bare_table = _build_bare_name_table()
    TOWN_FAMILY = {SegType.TOWN, SegType.VILLAGE, SegType.CITY, SegType.DISTRICT}

    candidates = set()
    for w, f in d1.items():
        if f >= args.min_freq and len(w) >= 2:
            if _d1_type_infer(w, bare_table) in TOWN_FAMILY:
                candidates.add(w)
    print(f"candidates (freq>={args.min_freq}, TOWN-family): {len(candidates):,}")
    trie = build_trie(candidates)
    rtrie = build_trie(w[::-1] for w in candidates)
    rev_map = {w[::-1]: w for w in candidates}

    start_cnt = {w: 0 for w in candidates}
    end_cnt = {w: 0 for w in candidates}
    total_names = 0
    for ci in range(args.chunks):
        path = os.path.join(DATA, "split", "poi", f"chunk_{ci:02d}.csv")
        if not os.path.exists(path):
            break
        with open(path, encoding="utf-8") as f:
            for line in f:
                name = line.rstrip("\n").split("\t")[0].strip()
                if not name:
                    continue
                total_names += 1
                h = prefix_hits(trie, name)
                if h:
                    start_cnt[h] += 1
                rh = suffix_hits(rtrie, name)
                if rh:
                    end_cnt[rev_map[rh]] += 1
        print(f"  scanned {path} (cum names: {total_names:,})", flush=True)

    actions = []
    for w in candidates:
        s, e = start_cnt[w], end_cnt[w]
        if e >= args.min_end and e >= args.end_rate * max(1, s + e):
            actions.append({"word": w, "action": "move", "freq": d1[w],
                            "start": s, "end": e,
                            "in_d4": w in d4, "sql_dominant": w in sql_dom})

    out = args.out or os.path.join(DICT_DIR, "poi_prune_v1.3.0.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(actions, f, ensure_ascii=False, indent=1)
    print(f"\nactions: move={len(actions)} -> {out}")
    for a in sorted(actions, key=lambda x: -x["end"])[:20]:
        print(f"  {a['word']}: d1_freq={a['freq']:,} start={a['start']} end={a['end']} "
              f"in_d4={a['in_d4']} sql={a['sql_dominant']}")


if __name__ == "__main__":
    main()
