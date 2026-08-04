#!/usr/bin/env python3
"""LOC 词典伪行政词条挖掘 → dicts/loc_prune_v1.3.0.json

规则 (保守): 词在 CITY/DISTRICT/TOWN 词典中, 且
  a) 不被 areas/ 五级区划证实 (精确名或 name+后缀形式)
  b) 行政词典 freq < 10000
  c) 同词在 POI 词典中 freq >= 100 × 行政freq
产出: 待删 (word, type) 列表 JSON, 由 v3 引擎加载时应用
"""
import csv
import json
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.types import SegType

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADMIN_SUFFIXES = ("省", "市", "区", "县", "旗", "镇", "乡", "街道", "自治县",
                  "自治州", "地区", "盟", "自治区", "民族乡", "苏木", "办事处")


def load_areas_attestation():
    attested = set()
    areas_dir = os.path.join(BASE, "data", "areas")
    for fname in ("provinces.csv", "cities.csv", "areas.csv", "streets.csv", "villages.csv"):
        path = os.path.join(areas_dir, fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                name = row.get("name", "").strip().strip('"')
                if not name:
                    continue
                attested.add(name)
                for sfx in ADMIN_SUFFIXES:
                    if name.endswith(sfx) and len(name) > len(sfx):
                        attested.add(name[:-len(sfx)])
                        break
    return attested


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dict", default="loc_v1.2.3.pkl")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    attested = load_areas_attestation()
    print(f"areas attested names: {len(attested):,}")

    with open(os.path.join(BASE, "dicts", args.dict), "rb") as f:
        loc = pickle.load(f)
    poi_dict = loc.get(SegType.POI, {})

    prune = []
    for st in (SegType.CITY, SegType.DISTRICT, SegType.TOWN):
        dd = loc.get(st, {})
        for word, freq in dd.items():
            if word in attested:
                continue
            if freq >= 10000:
                continue
            poi_freq = poi_dict.get(word, 0)
            if poi_freq >= 100 * max(1, freq):
                prune.append({"word": word, "type": st.value,
                              "admin_freq": freq, "poi_freq": poi_freq})

    out = args.out or os.path.join(BASE, "dicts", "loc_prune_v1.3.0.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(prune, f, ensure_ascii=False, indent=1)
    print(f"prune candidates: {len(prune)} -> {out}")
    for p in prune[:20]:
        print(f"  [{p['type']}] {p['word']}: admin={p['admin_freq']:,} poi={p['poi_freq']:,}")


if __name__ == "__main__":
    main()
