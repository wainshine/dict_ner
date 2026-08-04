"""LOC/ORG/POI 三套引擎配置 — 行为等价于 loc/org/poi 旧识别器

构造方式:
  build_loc_engine(dict_name="loc_v1.2.3")  → 等价 AddressRecognizer
  build_org_engine(version="v1.2.3")        → 等价 OrgDPRecognizer
  build_poi_engine(dict_name="poi_v1.2.3.pkl") → 等价 PoiRecognizer
"""
import csv
import os
import warnings

from core.types import SegType, ADMIN_SUFFIX_MAP, LEVEL_ORDER
from v3.engine.dp import DPEngine, EngineConfig

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE, "data")
DICT_DIR = os.path.join(BASE, "dicts")

_ADDR_TYPES = [SegType.PROVINCE, SegType.CITY, SegType.DISTRICT,
               SegType.TOWN, SegType.VILLAGE, SegType.COMMUNITY, SegType.ROAD]


def _loc_trans_table():
    table = {}
    valid = [
        (SegType.PROVINCE, SegType.CITY, 0.0),
        (SegType.PROVINCE, SegType.DISTRICT, 1.0),
        (SegType.CITY, SegType.DISTRICT, 0.0),
        (SegType.CITY, SegType.TOWN, 1.0),
        (SegType.CITY, SegType.ROAD, 2.0),
        (SegType.DISTRICT, SegType.TOWN, 0.0),
        (SegType.DISTRICT, SegType.ROAD, 1.0),
        (SegType.DISTRICT, SegType.VILLAGE, 1.0),
        (SegType.TOWN, SegType.VILLAGE, 0.0),
        (SegType.TOWN, SegType.COMMUNITY, 0.0),
        (SegType.TOWN, SegType.ROAD, 0.5),
        (SegType.TOWN, SegType.POI, 2.0),
        (SegType.VILLAGE, SegType.ROAD, 0.5),
        (SegType.VILLAGE, SegType.POI, 2.0),
        (SegType.COMMUNITY, SegType.ROAD, 0.5),
        (SegType.COMMUNITY, SegType.POI, 2.0),
        (SegType.ROAD, SegType.POI, 1.0),
        (SegType.ROAD, SegType.POI_SUB, 1.0),
        (SegType.ROAD, SegType.NUMERIC, 0.5),
        (SegType.ROAD, SegType.ORIENTATION, 0.2),
        (SegType.ROAD, SegType.LOCATION, 0.2),
        (SegType.POI, SegType.POI_SUB, 0.5),
        (SegType.POI, SegType.LOCATION, 0.3),
        (SegType.POI, SegType.ORIENTATION, 0.3),
        (SegType.ORIENTATION, SegType.ROAD, 0.0),
        (SegType.ORIENTATION, SegType.POI, 1.0),
        (SegType.ORIENTATION, SegType.LOCATION, 0.5),
        (SegType.LOCATION, SegType.ORIENTATION, 0.3),
        (SegType.NUMERIC, SegType.ROAD, 0.5),
        (SegType.NUMERIC, SegType.POI, 1.0),
        (SegType.NUMERIC, SegType.ORIENTATION, 0.3),
    ]
    for a, b, cost in valid:
        table[(a, b)] = cost
    for t in (SegType.ROAD, SegType.POI, SegType.POI_SUB, SegType.NUMERIC):
        table[(t, t)] = 1.0
    return table


LOC_POI_SUB_INJECT = {
    "号", "层", "楼", "栋", "幢", "单元", "室", "组", "队", "排", "间",
    "一层", "二层", "三层", "四层", "五层", "六层", "七层", "八层", "九层", "十层",
    "一楼", "二楼", "三楼", "四楼", "五楼", "六楼", "七楼", "八楼", "九楼", "十楼",
    "负一层", "负一楼",
}

LOC_NUMERIC_INJECT = set("0123456789０１２３４５６７８９")

LOC_EXTRA_TRANSITIONS = {
    (SegType.NUMERIC, SegType.POI_SUB): 0.2,
    (SegType.VILLAGE, SegType.NUMERIC): 0.5,
    (SegType.COMMUNITY, SegType.NUMERIC): 0.5,
    (SegType.TOWN, SegType.NUMERIC): 1.0,
    (SegType.POI, SegType.NUMERIC): 0.5,
    (SegType.NUMERIC, SegType.LOCATION): 0.3,
    (SegType.POI_SUB, SegType.NUMERIC): 0.5,
    (SegType.POI_SUB, SegType.POI_SUB): 1.0,
    (SegType.POI_SUB, SegType.POI): 1.0,
    (SegType.POI_SUB, SegType.LOCATION): 0.3,
    (SegType.POI_SUB, SegType.ORIENTATION): 0.3,
}


def _load_loc_prune(prune_path=None):
    import json
    path = prune_path or os.path.join(DICT_DIR, "loc_prune_v1.3.0.json")
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {(p["word"], p["type"]) for p in json.load(f)}


def _load_poi_prune(prune_path=None):
    import json
    path = prune_path or os.path.join(DICT_DIR, "poi_prune_v1.3.0.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return {p["word"]: p["freq"] for p in json.load(f)}


def _load_loc_dict_data(dict_name="loc_v1.2.3", baked=False, prune_path=None):
    import pickle
    path = os.path.join(DICT_DIR, f"{dict_name}.pkl")
    with open(path, "rb") as f:
        dict_data = {k: dict(v) for k, v in pickle.load(f).items()}
    if baked:
        return dict_data
    prune = _load_loc_prune(prune_path)
    for st, word_freqs in dict_data.items():
        for word in list(word_freqs):
            if (word, st.value) in prune:
                del word_freqs[word]
    poi_sub = dict_data.setdefault(SegType.POI_SUB, {})
    numeric = dict_data.setdefault(SegType.NUMERIC, {})
    existing = set()
    for word_freqs in dict_data.values():
        existing.update(word_freqs)
    for w in LOC_POI_SUB_INJECT:
        if w not in existing:
            poi_sub[w] = 80
    for w in LOC_NUMERIC_INJECT:
        if w not in existing:
            numeric[w] = 5000
    return dict_data


def build_loc_engine(dict_name="loc_v1.3.0", baked=None):
    if baked is None:
        baked = _is_baked(dict_name)
    dict_data = _load_loc_dict_data(dict_name, baked=baked)
    entries = []
    for seg_type, word_freqs in dict_data.items():
        for word, freq in word_freqs.items():
            entries.append((word, seg_type, freq))
    trans = _loc_trans_table()
    for k, v in LOC_EXTRA_TRANSITIONS.items():
        trans.setdefault(k, v)
    return DPEngine(EngineConfig(
        name="loc",
        entries=entries,
        trans_table=trans,
        start_costs={
            SegType.PROVINCE: 0.0, SegType.CITY: 1.0, SegType.DISTRICT: 2.0,
            SegType.TOWN: 2.0, SegType.VILLAGE: 3.0, SegType.COMMUNITY: 3.0,
            SegType.CHAR: 3.0,
        },
        word_cost_mode="loc",
        single_char_cost=3.0,
        single_char_type=SegType.CHAR,
        use_admin_patterns=True,
        use_location_patterns=True,
        post_hooks=("merge_orientation", "strip_road_conjunction",
                    "merge_location", "merge_same_type",
                    "assign_poi_types_loc"),
    ))


def _org_trans_table(allow_adjacent_d4):
    table = {}
    for a in _ADDR_TYPES:
        table[(SegType.UNKNOWN, a)] = 0.0
        for b in _ADDR_TYPES:
            table[(a, b)] = 0.0
        table[(a, SegType.UNKNOWN)] = 0.3
        table[(a, SegType.POI)] = 1.0
        table[(a, SegType.INDUSTRY)] = 0.5
    table[(SegType.UNKNOWN, SegType.POI)] = 2.0
    table[(SegType.UNKNOWN, SegType.UNKNOWN)] = 1.5
    table[(SegType.UNKNOWN, SegType.POI)] = 0.2
    table[(SegType.INDUSTRY, SegType.POI)] = 0.0
    table[(SegType.UNKNOWN, SegType.INDUSTRY)] = 0.3
    table[(SegType.INDUSTRY, SegType.INDUSTRY)] = 5.0
    table[(SegType.INDUSTRY, SegType.UNKNOWN)] = 1.0
    if allow_adjacent_d4:
        table[(SegType.POI, SegType.POI)] = 1.5
        table[(SegType.POI, SegType.UNKNOWN)] = 2.0
    return table


def _build_bare_name_table():
    table = {}
    areas_dir = os.path.join(DATA_DIR, "areas")
    suffix_to_type = {
        "维吾尔自治区": SegType.PROVINCE, "回族自治区": SegType.PROVINCE,
        "壮族自治区": SegType.PROVINCE, "特别行政区": SegType.PROVINCE,
        "省": SegType.PROVINCE, "自治区": SegType.PROVINCE,
        "市": SegType.CITY, "自治州": SegType.CITY, "地区": SegType.CITY, "盟": SegType.CITY,
        "自治县": SegType.DISTRICT, "自治旗": SegType.DISTRICT,
        "区": SegType.DISTRICT, "县": SegType.DISTRICT, "旗": SegType.DISTRICT,
        "办事处": SegType.TOWN, "民族乡": SegType.TOWN, "苏木": SegType.TOWN,
        "镇": SegType.TOWN, "乡": SegType.TOWN, "街道": SegType.TOWN,
    }
    for fname, default_type in [("provinces.csv", SegType.PROVINCE),
                                ("cities.csv", SegType.CITY),
                                ("areas.csv", SegType.DISTRICT),
                                ("streets.csv", SegType.TOWN)]:
        path = os.path.join(areas_dir, fname)
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    name = row.get("name", "").strip()
                    if not name or len(name) < 3:
                        continue
                    for sfx, stype in sorted(suffix_to_type.items(),
                                             key=lambda x: -len(x[0])):
                        if name.endswith(sfx) and len(name) > len(sfx):
                            bare = name[:-len(sfx)]
                            if len(bare) >= 2:
                                existing = table.get(bare)
                                if existing is None:
                                    table[bare] = stype
                                elif LEVEL_ORDER.get(stype, 99) < LEVEL_ORDER.get(existing, 99):
                                    table[bare] = stype
                            break
        except (FileNotFoundError, UnicodeDecodeError, csv.Error) as e:
            warnings.warn(f"Failed to load bare name table from {path}: {e}")
    return table


def _inject_d111_missing(d1_freqs):
    d111_path = os.path.join(DATA_DIR, "addr_segments_sql.csv")
    if not os.path.exists(d111_path):
        return
    SUFFIX_TYPE = {
        "自治县": SegType.DISTRICT, "自治旗": SegType.DISTRICT,
        "区": SegType.DISTRICT, "县": SegType.DISTRICT, "旗": SegType.DISTRICT,
        "镇": SegType.TOWN, "乡": SegType.TOWN,
    }
    GENERIC = {"新区", "东区", "南区", "西区", "北区", "中区",
               "城区", "片区", "园区", "矿区", "林区", "特区",
               "乡村", "城乡", "城镇", "山镇", "水乡", "山乡", "渔乡"}
    with open(d111_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            word = row["d1"].strip()
            if not word or len(word) < 2:
                continue
            if word in d1_freqs or word in GENERIC:
                continue
            try:
                tf = max(1, int(row.get("tf1", 0) or 0))
            except ValueError:
                tf = 1
            if tf < 20:
                continue
            for sfx, stype in sorted(SUFFIX_TYPE.items(), key=lambda x: -len(x[0])):
                if word.endswith(sfx) and len(word) > len(sfx):
                    d1_freqs[word] = max(d1_freqs.get(word, 0), tf)
                    break


def _d1_type_infer(word, bare_name_type):
    st = SegType.ROAD
    for t, suffixes in sorted(ADMIN_SUFFIX_MAP.items(), key=lambda x: -len(x[0].value)):
        for sfx in sorted(suffixes, key=lambda x: -len(x)):
            if word.endswith(sfx) and len(word) > len(sfx):
                st = t
                break
        if st != SegType.ROAD:
            break
    if st == SegType.ROAD and word in bare_name_type:
        st = bare_name_type[word]
    return st


def _inject_poi_seed(d4_freqs, seed_path):
    injected = []
    with open(seed_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            sfx = row["sfx"].strip()
            if not sfx or len(sfx) < 2 or sfx in d4_freqs:
                continue
            try:
                tf = int(row.get("tf1", 0) or 0)
            except ValueError:
                tf = 1
            if tf < 100:
                continue
            d4_freqs[sfx] = tf
            injected.append(sfx)
    return injected


def _load_sql_suffix_set():
    path = os.path.join(DATA_DIR, "suffix_segments_sql.csv")
    result = set()
    if not os.path.exists(path):
        return result
    with open(path, encoding="utf-8-sig") as f:
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


def _load_org_dicts(dict_name, version, apply_poi_prune=False, baked=False,
                    poi_seed_path=None, prune_path=None):
    import pickle
    if dict_name:
        cache_path = os.path.join(DICT_DIR, dict_name)
    else:
        cache_path = os.path.join(DICT_DIR, f"org_{version}.pkl")
        if not os.path.exists(cache_path):
            for fallback in ("v1.1.1", ""):
                fb = os.path.join(DICT_DIR,
                                  f"org_{fallback}.pkl" if fallback else "org.pkl")
                if os.path.exists(fb):
                    cache_path = fb
                    break
    d1_freqs, d3_freqs, d4_freqs = {}, {}, {}
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            cached = pickle.load(f)
        d1_freqs = dict(cached.get("d1_freqs", {}))
        d3_freqs = dict(cached.get("d3_freqs", {}))
        d4_freqs = dict(cached.get("d4_freqs", {}))

    if not baked:
        if apply_poi_prune:
            for w, fr in _load_poi_prune(prune_path).items():
                if w in d1_freqs:
                    d1_freqs.pop(w)
                    d4_freqs[w] = max(d4_freqs.get(w, 0), fr)

        sql_sfx = _load_sql_suffix_set()
        bare_name_type = _build_bare_name_table()
        for bare_name in bare_name_type:
            if bare_name not in d1_freqs and bare_name not in sql_sfx \
                    and bare_name not in d4_freqs:
                d1_freqs[bare_name] = 5000
        if not dict_name and version not in cache_path:
            _inject_d111_missing(d1_freqs)
        if poi_seed_path and os.path.exists(poi_seed_path):
            _inject_poi_seed(d4_freqs, poi_seed_path)

    return d1_freqs, d3_freqs, d4_freqs


def _build_org_like_engine(dict_name, version, disable_short_d4_penalty,
                           allow_adjacent_d4, poi_seed_path, name,
                           apply_poi_prune=False, baked=False):
    d1_freqs, d3_freqs, d4_freqs = _load_org_dicts(
        dict_name, version, apply_poi_prune=apply_poi_prune,
        baked=baked, poi_seed_path=poi_seed_path)

    bare_name_type = _build_bare_name_table()
    entries = []
    for w, fr in d1_freqs.items():
        entries.append((w, _d1_type_infer(w, bare_name_type), fr))
    for w, fr in d3_freqs.items():
        entries.append((w, SegType.INDUSTRY, fr))
    for w, fr in d4_freqs.items():
        entries.append((w, SegType.POI, fr))

    start_costs = {t: 0.0 for t in _ADDR_TYPES}
    start_costs[SegType.POI] = 0.2
    start_costs[SegType.UNKNOWN] = 1.5
    start_costs[SegType.INDUSTRY] = 0.3

    return DPEngine(EngineConfig(
        name=name,
        entries=entries,
        trans_table=_org_trans_table(allow_adjacent_d4),
        start_costs=start_costs,
        word_cost_mode="org",
        single_char_cost=2.0,
        single_char_type=SegType.UNKNOWN,
        short_d4_penalty=not disable_short_d4_penalty,
        post_hooks=("assign_poi_types", "merge_unknown", "trailing_single",
                    "leading_bracket", "relabel_brand"),
    ))


def _is_baked(name):
    for prefix in ("v1.3", "v1.4", "v1.5", "v1.6", "v1.7", "v1.8", "v1.9", "v2."):
        if prefix in name:
            return True
    return False


def build_org_engine(version="v1.3.0", baked=None):
    if baked is None:
        baked = _is_baked(version)
    return _build_org_like_engine(
        dict_name=None, version=version,
        disable_short_d4_penalty=False, allow_adjacent_d4=False,
        poi_seed_path=None, name="org", baked=baked)


def build_poi_engine(dict_name="poi_v1.3.0.pkl", baked=None):
    if baked is None:
        baked = _is_baked(dict_name)
    seed_path = os.path.join(DATA_DIR, "suffix_seed.csv")
    return _build_org_like_engine(
        dict_name=dict_name, version="v1.1.2",
        disable_short_d4_penalty=True, allow_adjacent_d4=True,
        poi_seed_path=seed_path if os.path.exists(seed_path) else None,
        name="poi", apply_poi_prune=True, baked=baked)
