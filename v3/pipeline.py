"""v3 统一总线 — 新 DPEngine ×3 + 自包含后处理与查表 (v4.0.0 起不再依赖 v2 pipeline)

段识别由 v3.engine 提供 (与旧识别器 20K 样本零差异, 见 engine/gate.py)。
复合机构检测/过度拆分合并/ORG_SUFFIX remap 逻辑复制自 v2 pipeline.py (逐方法不改逻辑)。
"""
import csv
import logging
import os
import pickle
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import AddressResult, SegType
from v3.engine.configs import build_loc_engine, build_org_engine, build_poi_engine

logger = logging.getLogger(__name__)

COMPANY_SUFFIXES = {
    "公司", "有限公司", "有限责任公司", "股份有限公司",
    "集团", "企业", "总公司", "分公司", "子公司",
}

GOV_SUFFIXES = {
    "卫健委", "卫生健康委", "卫生健康局", "管理局", "事务局", "监督局",
    "办公室", "办事处", "管理处", "管理所", "监督所",
    "监察委", "监察委员会", "管委会", "管理委员会",
    "指挥部", "工作站", "政务服务中心", "行政服务中心",
    "派出所", "村委会", "人民政府", "居委会", "警务室",
    "工商所", "税务所", "税务局", "联合会", "协会", "党支部",
}

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "data")
DICT_DIR = os.path.join(BASE, "dicts")


class _OrgAdapter:
    def __init__(self, engine, brand_model):
        self._engine = engine
        self._brand = brand_model

    def recognize(self, text):
        return self._engine.recognize(text)

    def brand_score(self, text):
        return self._brand.brand_score(text)


class V3Pipeline:
    def __init__(self, loc_dict="loc_v1.5.0", org_version="v1.5.0",
                 poi_dict="poi_v1.5.0.pkl", brand_version="v1.5.0"):
        from v3.brand_model import BrandModel
        brand = BrandModel(DICT_DIR, version=brand_version)
        if not brand.load():
            logger.warning("brand model missing: %s; brand_score falls back to 0.5",
                           brand._path)
        self._loc_engine = build_loc_engine(loc_dict)
        self._poi_engine = build_poi_engine(poi_dict)
        self.org = _OrgAdapter(build_org_engine(org_version), brand)
        self._lock = threading.Lock()
        self._d4_map = None
        self._suffix_table = None
        self._sql_suffixes = None

    @property
    def loc(self):
        return self._loc_engine

    @property
    def poi(self):
        return self._poi_engine

    @property
    def d4_map(self):
        if self._d4_map is None:
            with self._lock:
                if self._d4_map is None:
                    path = os.path.join(DICT_DIR, "d4_category_map.pkl")
                    if os.path.exists(path):
                        with open(path, "rb") as f:
                            self._d4_map = pickle.load(f)
                    else:
                        logger.warning("d4_category_map.pkl 缺失, d4 类别特征置空 (静默降级): %s", path)
                        self._d4_map = {}
        return self._d4_map

    @property
    def suffix_table(self):
        if self._suffix_table is None:
            with self._lock:
                if self._suffix_table is None:
                    self._suffix_table = {}
                    path = os.path.join(DICT_DIR, "suffix_category_gaode.csv")
                    if os.path.exists(path):
                        with open(path, encoding="utf-8-sig") as f:
                            for row in csv.DictReader(f):
                                sfx = row["suffix"]
                                cat = row["gaode_category"]
                                self._suffix_table[sfx] = cat
                    else:
                        logger.warning("suffix_category_gaode.csv 缺失, 后缀类别特征置空 (静默降级): %s", path)
        return self._suffix_table

    @property
    def sql_suffixes(self):
        if self._sql_suffixes is None:
            with self._lock:
                if self._sql_suffixes is None:
                    self._sql_suffixes = set()
                    path = os.path.join(DATA_DIR, "suffix_segments_sql.csv")
                    if os.path.exists(path):
                        with open(path, encoding="utf-8-sig") as f:
                            for row in csv.DictReader(f):
                                sfx = row["d4"].strip()
                                if sfx and len(sfx) >= 2:
                                    self._sql_suffixes.add(sfx)
                    else:
                        logger.warning("suffix_segments_sql.csv 缺失, SQL 后缀验证置空 (静默降级): %s", path)
        return self._sql_suffixes

    def _has_company_suffix(self, org_result):
        for s in org_result.segments:
            for sfx in COMPANY_SUFFIXES:
                if s.text.endswith(sfx):
                    return True
        return False

    def _remap_org_segments(self, result):
        if result and result.segments:
            for s in result.segments:
                if s.seg_type == SegType.POI:
                    s.seg_type = SegType.ORG_SUFFIX
        return result

    def _merge_over_split(self, segments):
        from core.csv_index import CsvIndex
        idx = CsvIndex.instance()
        addr_types = {SegType.PROVINCE, SegType.CITY, SegType.DISTRICT,
                      SegType.TOWN, SegType.VILLAGE, SegType.COMMUNITY, SegType.ROAD}
        no_merge_types = {SegType.ORG_SUFFIX, SegType.POI}

        i = 0
        while i < len(segments) - 1:
            s1, s2 = segments[i], segments[i + 1]
            if s1.seg_type in addr_types or s2.seg_type in addr_types:
                i += 1
                continue
            if s1.seg_type in no_merge_types or s2.seg_type in no_merge_types:
                i += 1
                continue
            merged = s1.text + s2.text
            if merged in idx.suffix or merged in idx.trade:
                s1.text = merged
                s1.seg_type = SegType.INDUSTRY
                del segments[i + 1]
                continue
            i += 1
        return segments

    def _detect_compound(self, segments):
        company_suffixes = {"有限公司", "有限责任公司", "股份有限公司"}
        for i, s in enumerate(segments):
            if i == len(segments) - 1:
                continue
            if s.seg_type == SegType.ORG_SUFFIX and s.text in company_suffixes:
                return s.end
        return None

    def _re_split_and_recognize(self, text, split_pos):
        part1 = text[:split_pos]
        part2 = text[split_pos:]
        res1 = self._remap_org_segments(self.org.recognize(part1))
        res2 = self._remap_org_segments(self.org.recognize(part2))
        merged = res1.segments + res2.segments
        for i, s in enumerate(merged):
            s.start = 0 if i == 0 else merged[i - 1].end
            s.end = s.start + len(s.text)
        return AddressResult(original=text, segments=merged)

    def recognize(self, text: str):
        """三体系段切分视图 (与 v2 pipeline.recognize 输出契约一致)"""
        text = text.strip()
        loc_result = self.loc.recognize(text)
        org_result = self._remap_org_segments(self.org.recognize(text))
        org_result.segments = self._merge_over_split(org_result.segments)
        split_pos = self._detect_compound(org_result.segments)
        if split_pos is not None:
            org_result = self._re_split_and_recognize(text, split_pos)

        is_company = self._has_company_suffix(org_result)
        poi_result = None if is_company else self.poi.recognize(text)

        return {
            "text": text,
            "loc": loc_result.to_dict(),
            "org": org_result.to_dict(),
            "poi": poi_result.to_dict() if poi_result else None,
        }

    def recognize_simple(self, text: str):
        """Simple segment output for CLI display."""
        r = self.recognize(text)
        lines = [f"输入: {r['text']}"]
        for label, key in [("地名", "loc"), ("机构", "org"), ("POI", "poi")]:
            if r[key] and r[key].get("segments"):
                segs = " | ".join(
                    f"[{s['type']}]「{s['text']}」"
                    for s in r[key]["segments"]
                )
                lines.append(f"  {label}: {segs}")
        return "\n".join(lines)
