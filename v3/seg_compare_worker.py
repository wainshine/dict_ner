#!/usr/bin/env python3
"""全量段对比 worker — 旧版识别器 vs v1.3.0 实体化引擎, 逐条段差异统计

用法: python v3/seg_compare_worker.py <org|poi|loc> <chunk_csv> <out_json>
输出: {total, diff, type_old{type:count}, type_new{type:count}, examples[[name,old,new]...]}
"""
import csv
import json
import os
import sys
from collections import Counter

csv.field_size_limit(sys.maxsize)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")


def build_old(system):
    if system == "org":
        from org.recognizer import OrgDPRecognizer
        return OrgDPRecognizer(DATA, version="v1.2.3")
    if system == "poi":
        from poi.recognizer import PoiRecognizer
        return PoiRecognizer(DATA, dict_name="poi_v1.2.3.pkl")
    from loc.builder import DictBuilder
    from loc.recognizer import AddressRecognizer
    b = DictBuilder.load(os.path.join(BASE, "dicts"), "loc_v1.2.3")
    return AddressRecognizer(b.dict_data)


def build_new(system):
    from v3.engine.configs import build_org_engine, build_poi_engine, build_loc_engine
    if system == "org":
        return build_org_engine("v1.3.0")
    if system == "poi":
        return build_poi_engine("poi_v1.3.0.pkl")
    return build_loc_engine("loc_v1.3.0")


def build_v143(system):
    from v3.engine.configs import build_org_engine, build_poi_engine, build_loc_engine
    if system == "org":
        return build_org_engine("v1.4.3")
    if system == "poi":
        return build_poi_engine("poi_v1.4.3.pkl")
    return build_loc_engine("loc_v1.4.3")


def build_v150(system):
    from v3.engine.configs import build_org_engine, build_poi_engine, build_loc_engine
    if system == "org":
        return build_org_engine("v1.5.0")
    if system == "poi":
        return build_poi_engine("poi_v1.5.0.pkl")
    return build_loc_engine("loc_v1.5.0")


def build_v140(system):
    from v3.engine.configs import build_org_engine, build_poi_engine, build_loc_engine
    if system == "org":
        return build_org_engine("v1.4.0")
    if system == "poi":
        return build_poi_engine("poi_v1.4.0.pkl")
    return build_loc_engine("loc_v1.4.0")


def main():
    system, chunk_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    mode = sys.argv[4] if len(sys.argv) > 4 else "legacy_vs_v130"
    if mode == "v143_vs_v150":
        old = build_v143(system)
        new = build_v150(system)
    elif mode == "v130_vs_v140":
        old = build_new(system)
        new = build_v140(system)
    else:
        old = build_old(system)
        new = build_new(system)

    total = 0
    diff = 0
    type_old = Counter()
    type_new = Counter()
    examples = []
    with open(chunk_path, encoding="utf-8") as f:
        if system == "poi":
            rows = (line.rstrip("\n").split("\t")[0].strip() for line in f)
        else:
            import itertools
            reader = csv.reader(f)
            first = next(reader, None)
            rest = (row[0] for row in reader if row)
            if first and first[0] and first[0] != "dict":
                rows = itertools.chain([first[0]], rest)
            else:
                rows = rest
        for name in rows:
            if not name:
                continue
            total += 1
            s_old = [(s.text, s.seg_type.value) for s in old.recognize(name).segments]
            s_new = [(s.text, s.seg_type.value) for s in new.recognize(name).segments]
            for _, t in s_old:
                type_old[t] += 1
            for _, t in s_new:
                type_new[t] += 1
            if s_old != s_new:
                diff += 1
                if len(examples) < 30:
                    examples.append([name, s_old, s_new])
            if total % 500000 == 0:
                print(f"[{os.path.basename(out_path)}] {total:,}", flush=True)

    result = {"system": system, "chunk": os.path.basename(chunk_path),
              "total": total, "diff": diff,
              "type_old": dict(type_old), "type_new": dict(type_new),
              "examples": examples}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    print(f"[{os.path.basename(out_path)}] DONE total={total:,} diff={diff:,} "
          f"({100*diff/max(1,total):.2f}%)", flush=True)


if __name__ == "__main__":
    main()
