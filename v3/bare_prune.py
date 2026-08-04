#!/usr/bin/env python3
"""bare 裸名位置证据 — 区分"真镇名"与"品牌词"

原理: bare 注入词若真作地址用, 应在名称开头出现 (深圳市[幸福]路 vs [幸福]果源公司)。
统计 bare_name_type 全部条目在 split/org 语料中的开头/结尾出现次数:
  - start≈0 且 end>=100 且 end>=80%*(start+end): 品牌主导 → 降频 5000→500
  - 其余: 保留 5000
产出: dicts/bare_prune_v1.4.3.json
用法: python v3/bare_prune.py [--chunks 2] [--min-end 100]
"""
import argparse
import json
import os
import sys

csv_module = __import__("csv")
csv_module.field_size_limit(sys.maxsize)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
DICT_DIR = os.path.join(BASE, "dicts")


def build_trie(words):
    trie = {}
    for w in words:
        node = trie
        for ch in w:
            node = node.setdefault(ch, {})
        node["#"] = w
    return trie


def walk(trie, text):
    node = trie
    for ch in text:
        if ch not in node:
            return None
        node = node[ch]
        if "#" in node:
            return node["#"]
    return node.get("#")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=2)
    ap.add_argument("--min-end", type=int, default=100)
    ap.add_argument("--end-rate", type=float, default=0.8)
    args = ap.parse_args()

    from v3.engine.configs import _build_bare_name_table
    bare_table = _build_bare_name_table()
    candidates = set(bare_table)
    print(f"bare candidates: {len(candidates):,}")

    trie = build_trie(candidates)
    rtrie = build_trie(w[::-1] for w in candidates)
    rev = {w[::-1]: w for w in candidates}
    start_cnt = {w: 0 for w in candidates}
    end_cnt = {w: 0 for w in candidates}
    total = 0
    for ci in range(args.chunks):
        path = os.path.join(DATA, "split", "org", f"chunk_{ci:02d}.csv")
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i == 0 and line.startswith("dict"):
                    continue
                name = line.strip().rsplit(",", 5)[0].strip()
                if not name:
                    continue
                total += 1
                h = walk(trie, name)
                if h:
                    start_cnt[h] += 1
                rh = walk(rtrie, name[::-1])
                if rh:
                    end_cnt[rev[rh]] += 1
        print(f"  scanned chunk_{ci:02d} (cum {total:,})", flush=True)

    demote = []
    keep = 0
    for w in candidates:
        s, e = start_cnt[w], end_cnt[w]
        if e >= args.min_end and e >= args.end_rate * max(1, s + e):
            demote.append({"word": w, "start": s, "end": e,
                           "type": bare_table[w].value})
        else:
            keep += 1
    demote.sort(key=lambda x: -x["end"])
    out = os.path.join(DICT_DIR, "bare_prune_v1.4.3.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(demote, f, ensure_ascii=False, indent=1)
    print(f"\ndemote: {len(demote)}, keep: {keep} -> {out}")
    for a in demote[:20]:
        print(f"  {a['word']} [{a['type']}]: start={a['start']} end={a['end']}")


if __name__ == "__main__":
    main()
