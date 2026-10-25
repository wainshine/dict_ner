#!/usr/bin/env python3
"""词典实体化 v1.3.0 — 把加载层补丁烘焙进 pkl

org_v1.3.0.pkl:  v1.2.3 + bare注入(sql_sfx/d4互斥) 快照
poi_v1.3.0.pkl:  v1.2.3 + poi_prune(203词 d1→d4) + bare互斥 + poi seed 快照
loc_v1.3.0.pkl:  v1.2.3 + loc_prune(36词删除) + NUMERIC/POI_SUB注入 快照

产出后引擎以 baked=True 加载, 运行时不再打补丁。
门禁: 补丁引擎 vs 实体化引擎 零差异 (见 v3/engine/gate.py --baked-compare)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.pipeline_base import atomic_pickle_dump

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_DIR = os.path.join(BASE, "dicts")
DATA = os.path.join(BASE, "data")


def main():
    from v3.engine.configs import _load_org_dicts, _load_loc_dict_data

    d1, d3, d4 = _load_org_dicts(None, "v1.2.3", baked=False)
    out = os.path.join(DICT_DIR, "org_v1.3.0.pkl")
    atomic_pickle_dump({"d1_freqs": d1, "d3_freqs": d3, "d4_freqs": d4}, out)
    print(f"org_v1.3.0: d1={len(d1):,} d3={len(d3):,} d4={len(d4):,} "
          f"({os.path.getsize(out)/1024/1024:.1f}MB)")

    seed = os.path.join(DATA, "suffix_seed.csv")
    d1, d3, d4 = _load_org_dicts("poi_v1.2.3.pkl", "v1.1.2", apply_poi_prune=True,
                                 baked=False,
                                 poi_seed_path=seed if os.path.exists(seed) else None)
    out = os.path.join(DICT_DIR, "poi_v1.3.0.pkl")
    atomic_pickle_dump({"d1_freqs": d1, "d3_freqs": d3, "d4_freqs": d4}, out)
    print(f"poi_v1.3.0: d1={len(d1):,} d3={len(d3):,} d4={len(d4):,} "
          f"({os.path.getsize(out)/1024/1024:.1f}MB)")

    dict_data = _load_loc_dict_data("loc_v1.2.3", baked=False)
    out = os.path.join(DICT_DIR, "loc_v1.3.0.pkl")
    atomic_pickle_dump(dict_data, out)
    sizes = {k.value: len(v) for k, v in dict_data.items()}
    print(f"loc_v1.3.0: {sizes} ({os.path.getsize(out)/1024/1024:.1f}MB)")


if __name__ == "__main__":
    main()
