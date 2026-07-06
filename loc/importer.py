"""新数据源 — areas/五级行政区划 + loc3.6kw"""

import os, csv, time
import logging
from collections import Counter, defaultdict
from typing import Dict, List, Tuple
from core.types import SegType, ADMIN_SUFFIX_MAP, POI_SUFFIX_MAP
from core.suffix_matcher import find_suffix_boundaries


# Village name normalization patterns
VILLAGE_NORMALIZE = [
    ("社区居民委员会", "社区"),
    ("社区居委会", "社区"),
    ("居民委员会", "社区"),
    ("村民委员会", "村"),
    ("村村委会", "村"),
    ("社区村民委员会", "村"),
]


def classify_suffix(sfx: str) -> str:
    for kw, cat in sorted(POI_SUFFIX_MAP.items(), key=lambda x: -len(x[0])):
        if len(kw) == 1:
            if sfx == kw:
                return cat
        elif sfx.endswith(kw):
            return cat
    return "建筑"


def normalize_village_name(name: str) -> List[str]:
    results = {name}
    accumulated = name
    for pattern, replacement in sorted(VILLAGE_NORMALIZE, key=lambda x: -len(x[0])):
        if pattern in accumulated:
            accumulated = accumulated.replace(pattern, replacement)
            if len(accumulated) >= 2:
                results.add(accumulated)
    return list(results)


def import_areas(data_dir: str) -> Dict[SegType, Dict[str, int]]:
    """Import five-level admin division data, return {type: {name: freq}}.
    Pseudo-frequencies: 1000 for confirmed admin names, 800 for village/community.
    """
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
    logger.info(f"  Imported areas: {counts}")
    return result


def import_loc36kw(data_dir: str) -> Dict[SegType, Counter]:
    """Import loc_corpus.csv, split compound entries, return {type: Counter(entry: idf)}."""
    path = os.path.join(data_dir, "loc_corpus.csv")
    logger.info(f"  Importing loc_corpus.csv ({os.path.getsize(path)/1024/1024:.0f}MB)...")
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

    logger.info(f"    {raw:,} rows → {split:,} split ({time.time()-t0:.0f}s)")
    for t, c in counters.items():
        logger.info(f"    {t.value:15s}: {len(c):>10,} unique")
    return counters


def _split_admin(text: str) -> List[Tuple[str, SegType]]:
    boundaries = find_suffix_boundaries(text, ADMIN_SUFFIX_MAP)
    if not boundaries:
        return []

    components = []
    start = 0
    for end, _spos, _sfx, stype in boundaries:
        comp = text[start:end]
        if comp and len(comp) > 1:
            components.append((comp, stype))
        start = end
    return components
