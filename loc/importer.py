"""新数据源 — areas/五级行政区划 + loc3.6kw"""

import os, csv, time
from collections import Counter, defaultdict
from typing import Dict, List, Tuple
from core.types import SegType, ADMIN_SUFFIX_MAP


# Village name normalization patterns
VILLAGE_NORMALIZE = [
    ("社区居民委员会", "社区"),
    ("社区居委会", "社区"),
    ("居民委员会", "社区"),
    ("村民委员会", "村"),
    ("村村委会", "村"),
    ("社区村民委员会", "村"),
]


# d444 suffix → category mapping (same as before, kept for classify_suffix)
SUFFIX_TO_CATEGORY = {
    "医院": "医院", "卫生院": "医院", "诊所": "医院", "医务室": "医院",
    "卫生室": "医院", "卫生所": "医院", "大药房": "医院", "药店": "医院",
    "门诊部": "医院", "医疗": "医院", "药房": "医院", "卫生站": "医院",
    "大学": "学校", "中学": "学校", "小学": "学校", "学院": "学校",
    "幼儿园": "学校", "学校": "学校", "培训": "学校", "教育": "学校",
    "托管": "学校", "托儿所": "学校", "辅导": "学校",
    "酒店": "酒店", "宾馆": "酒店", "旅馆": "酒店", "招待所": "酒店",
    "客栈": "酒店", "民宿": "酒店", "旅社": "酒店",
    "饭店": "餐饮", "餐厅": "餐饮", "酒楼": "餐饮", "饭馆": "餐饮",
    "食堂": "餐饮", "小吃": "餐饮", "面馆": "餐饮", "火锅": "餐饮",
    "烧烤": "餐饮", "快餐": "餐饮",
    "银行": "金融", "信用社": "金融", "保险": "金融", "证券": "金融",
    "政府": "政府", "派出所": "政府", "公安局": "政府",
    "法院": "政府", "检察院": "政府", "办事处": "政府", "大队": "政府",
    "中队": "政府", "支队": "政府",
    "车站": "交通", "火车站": "交通", "汽车站": "交通", "地铁站": "交通",
    "机场": "交通", "加油站": "交通", "收费站": "交通", "驾校": "交通",
    "超市": "商场", "商场": "商场", "百货": "商场", "商城": "商场",
    "市场": "商场", "购物": "商场",
    "大厦": "建筑", "大楼": "建筑", "广场": "建筑", "中心": "建筑",
    "花园": "住宅", "小区": "住宅", "家园": "住宅", "新村": "住宅",
    "新城": "住宅", "公寓": "住宅", "别墅": "住宅",
    "公园": "景点", "景区": "景点", "寺": "景点", "庙": "景点",
    "陵园": "景点", "博物馆": "景点", "纪念馆": "景点",
    "度假村": "旅游", "山庄": "旅游", "乐园": "旅游",
    "工厂": "工业", "厂": "工业", "车间": "工业", "制造": "工业",
    "加工": "工业", "机械厂": "工业",
    "农场": "农业", "合作社": "农业", "养殖": "农业", "种植": "农业",
    "水库": "水利", "电站": "能源", "泵站": "水利",
    "公司": "商业", "有限公司": "商业", "集团": "商业", "企业": "商业",
    "店": "商业", "铺": "商业", "商行": "商业",
    "局": "政府", "所": "政府", "委": "政府", "部": "政府", "会": "政府",
    "苑": "住宅", "庭": "住宅", "阁": "住宅",
    "城": "建筑", "园": "景点", "行": "商业",
}


def classify_suffix(sfx: str) -> str:
    for kw, cat in sorted(SUFFIX_TO_CATEGORY.items(), key=lambda x: -len(x[0])):
        if sfx.endswith(kw):
            return cat
    return "建筑"


def normalize_village_name(name: str) -> List[str]:
    """Return both original and normalized forms of a village name."""
    results = {name}
    for pattern, replacement in VILLAGE_NORMALIZE:
        if pattern in name:
            norm = name.replace(pattern, replacement)
            if norm != name and len(norm) >= 2:
                results.add(norm)
    return list(results)


def import_areas(data_dir: str) -> Dict[SegType, Dict[str, int]]:
    """Import five-level admin division data, return {type: {name: freq}}."""
    areas_dir = os.path.join(data_dir, "areas")
    result = defaultdict(dict)

    # Province
    path = os.path.join(areas_dir, "provinces.csv")
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = row["name"].strip()
            if name:
                result[SegType.PROVINCE][name] = 1000

    # City
    path = os.path.join(areas_dir, "cities.csv")
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = row["name"].strip()
            if name and name not in ("市辖区", "县", "市"):
                result[SegType.CITY][name] = 1000

    # District (area)
    path = os.path.join(areas_dir, "areas.csv")
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = row["name"].strip()
            if name:
                result[SegType.DISTRICT][name] = 1000

    # Town / Street
    path = os.path.join(areas_dir, "streets.csv")
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = row["name"].strip()
            if name:
                result[SegType.TOWN][name] = 1000

    # Village / Community (with normalization)
    path = os.path.join(areas_dir, "villages.csv")
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = row["name"].strip()
            if not name:
                continue
            names = normalize_village_name(name)
            for n in names:
                if "社区" in n:
                    result[SegType.COMMUNITY][n] = 800
                elif "村" in n:
                    result[SegType.VILLAGE][n] = 800

    counts = {k: len(v) for k, v in result.items()}
    print(f"  Imported areas: {counts}")
    return result


def import_loc36kw(data_dir: str) -> Dict[SegType, Counter]:
    """Import loc_corpus.csv, split compound entries, return {type: Counter(entry: idf)}."""
    path = os.path.join(data_dir, "loc_corpus.csv")
    print(f"  Importing loc_corpus.csv ({os.path.getsize(path)/1024/1024:.0f}MB)...")
    t0 = time.time()

    counters = defaultdict(Counter)
    raw = 0
    split = 0

    with open(path, encoding="gbk", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw += 1
            # Format: dict,idf
            parts = line.rsplit(",", 1)
            if len(parts) != 2:
                continue
            text, idf_str = parts[0].strip(), parts[1].strip()
            if not text or len(text) < 2:
                continue
            try:
                idf = max(1, int(float(idf_str)))
            except ValueError:
                idf = 1

            components = _split_admin(text)
            if components:
                if len(components) == 1:
                    comp, stype = components[0]
                    counters[stype][comp] += idf
                else:
                    split += 1
                    for comp, stype in components:
                        counters[stype][comp] += idf

            if raw % 5000000 == 0:
                print(f"    {raw//10000:>4}w rows, split={split:,}, "
                      f"POI={len(counters[SegType.POI]):,}")

    print(f"    {raw:,} rows → {split:,} split ({time.time()-t0:.0f}s)")
    for t, c in counters.items():
        print(f"    {t.value:15s}: {len(c):>10,} unique")
    return counters


def _split_admin(text: str) -> List[Tuple[str, SegType]]:
    """Same logic as DictBuilder._split_by_admin_suffixes."""
    all_boundaries = []
    for stype, sfx_set in ADMIN_SUFFIX_MAP.items():
        for sfx in sfx_set:
            pos = text.find(sfx)
            while pos >= 0:
                end = pos + len(sfx)
                all_boundaries.append((end, sfx, stype, pos))
                pos = text.find(sfx, end)

    if not all_boundaries:
        return []

    all_boundaries.sort(key=lambda x: (x[0], -len(x[1])))
    merged = []
    for end, sfx, stype, spos in all_boundaries:
        if not merged:
            merged.append((end, sfx, stype))
            continue
        prev_end, prev_sfx, prev_type = merged[-1]
        if end <= prev_end or spos < prev_end:
            if len(sfx) > len(prev_sfx):
                merged[-1] = (end, sfx, stype)
            continue
        merged.append((end, sfx, stype))

    components = []
    start = 0
    for end, sfx, stype in merged:
        comp = text[start:end]
        if comp and len(comp) > 1:
            components.append((comp, stype))
        start = end
    return components
