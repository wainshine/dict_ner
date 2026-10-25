"""v3 特征提取 — 从三识别器段输出+查表+统计信号构建固定维度特征向量

训练/推理同一代码路径, 特征顺序由 FEATURE_NAMES 固定。
缺失值用 np.nan (HistGradientBoosting 原生支持)。
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import SegType
from core.csv_index import CsvIndex
from v3.pipeline import COMPANY_SUFFIXES, GOV_SUFFIXES

D4_CATEGORIES = ("ORG", "POI_FAC", "POI_STORE", "ADDR", "AMBIGUOUS", "UNKNOWN")

_ADDR_TYPES = {
    SegType.PROVINCE, SegType.CITY, SegType.DISTRICT,
    SegType.TOWN, SegType.VILLAGE, SegType.COMMUNITY, SegType.ROAD,
}
_GEO_SEG_TYPES = _ADDR_TYPES | {SegType.LOCATION, SegType.ORIENTATION}

TEXT_FEATURES = ["len", "n_digit", "n_latin", "all_chinese"]

LOC_FEATURES = [
    "loc_n_segs", "loc_admin_cov", "loc_geo_cov",
    "loc_n_province", "loc_n_city", "loc_n_district", "loc_n_town",
    "loc_n_village", "loc_n_community", "loc_n_road",
    "loc_road_cov", "loc_has_location", "loc_has_orientation",
]

ORG_FEATURES = [
    "org_n_segs", "org_n_brand", "org_n_industry", "org_brand_cov",
    "org_has_poi_terminal", "org_last_is_brand", "org_last_is_industry",
    "has_comp", "has_gov", "has_industry", "double_negative",
    "d4_len", "d4_in_sql",
    "d4_map_confidence", "d4_map_gaode_freq_log",
    "sfx_aff_org_ratio", "sfx_aff_loc_ratio",
    "trd_aff_org_ratio", "trd_aff_loc_ratio",
    "org_brand_score",
]

POI_FEATURES = [
    "poi_n_segs", "poi_n_brand", "poi_n_industry", "poi_brand_cov",
    "poi_has_poi_terminal", "poi_last_is_brand", "poi_last_is_industry",
    "poi_d4_len", "poi_d4_in_sql",
    "poi_d4_map_confidence", "poi_d4_map_gaode_freq_log",
    "poi_sfx_aff_org_ratio", "poi_sfx_aff_loc_ratio",
    "poi_brand_score",
]

ADDR_AFF_FEATURES = ["addr_aff_org_ratio", "addr_aff_loc_ratio", "d1_prefix_len"]

FEATURE_NAMES = (
    TEXT_FEATURES + LOC_FEATURES + ORG_FEATURES + POI_FEATURES + ADDR_AFF_FEATURES
    + [f"d4_cat_{c}" for c in D4_CATEGORIES]
    + [f"d4_sfxcat_{c}" for c in D4_CATEGORIES]
    + [f"poi_d4_cat_{c}" for c in D4_CATEGORIES]
    + [f"poi_d4_sfxcat_{c}" for c in D4_CATEGORIES]
)

FEATURE_VERSION = "v3.0-feat1"


class FeatureExtractor:
    def __init__(self, pipe=None):
        if pipe is None:
            from v3.pipeline import V3Pipeline
            pipe = V3Pipeline()
        self.pipe = pipe
        self.idx = CsvIndex.instance()
        self.last_results = None

    def _lookup_suffix_category(self, d4):
        if not d4 or not self.pipe.suffix_table:
            return None
        for end in range(len(d4), 0, -1):
            for start in range(0, end):
                w = d4[start:end]
                if w in self.pipe.suffix_table:
                    return self.pipe.suffix_table[w]
        return None

    def _double_negative(self, d4):
        if not d4 or len(d4) < 2:
            return False
        for slen in range(min(4, len(d4) - 1), 1, -1):
            prefix = d4[:-slen]
            if prefix and d4 not in self.idx.suffix and prefix not in self.idx.trade:
                return True
        return False

    def _d4_info(self, segments, terminal_type):
        if not segments:
            return None
        last = segments[-1]
        if last.seg_type == terminal_type:
            return last.text
        cat = self.pipe.d4_map.get(last.text)
        if cat and cat.get("category") not in ("AMBIGUOUS", "UNKNOWN"):
            return last.text
        if self._lookup_suffix_category(last.text) is not None:
            return last.text
        return None

    def _fill_d4_feats(self, f, prefix, d4):
        f[f"{prefix}_len"] = len(d4) if d4 else 0
        f[f"{prefix}_in_sql"] = float(d4 in self.pipe.sql_suffixes) if d4 else np.nan
        entry = self.pipe.d4_map.get(d4) if d4 else None
        cat = entry.get("category") if entry else None
        f[f"{prefix}_map_confidence"] = entry.get("confidence", np.nan) if entry else np.nan
        f[f"{prefix}_map_gaode_freq_log"] = (
            np.log1p(entry.get("gaode_freq", 0)) if entry else np.nan)
        cat_key = "d4_cat" if prefix == "d4" else "poi_d4_cat"
        for c in D4_CATEGORIES:
            f[f"{cat_key}_{c}"] = float(cat == c) if cat else 0.0
        sfx_cat = self._lookup_suffix_category(d4) if d4 else None
        sfx_key = "d4_sfxcat" if prefix == "d4" else "poi_d4_sfxcat"
        for c in D4_CATEGORIES:
            f[f"{sfx_key}_{c}"] = float(sfx_cat == c) if sfx_cat else 0.0

    def extract_with_results(self, text):
        """提取特征, 同时返回本次调用的三体系段结果 (无共享状态)。

        并发调用安全: 所有识别结果都是局部变量, 不写入 self。
        """
        p = self.pipe
        text = text.strip()
        n = max(1, len(text))
        f = {}

        f["len"] = len(text)
        f["n_digit"] = sum(1 for ch in text if ch.isdigit())
        f["n_latin"] = sum(1 for ch in text if ch.isascii() and ch.isalpha())
        f["all_chinese"] = float(all("一" <= ch <= "鿿" for ch in text))

        loc_res = p.loc.recognize(text)
        org_res = p._remap_org_segments(p.org.recognize(text))
        org_res.segments = p._merge_over_split(org_res.segments)
        split_pos = p._detect_compound(org_res.segments)
        if split_pos is not None:
            org_res = p._re_split_and_recognize(text, split_pos)
        has_comp = p._has_company_suffix(org_res)
        poi_res = None if has_comp else p.poi.recognize(text)

        loc_segs = loc_res.segments
        f["loc_n_segs"] = len(loc_segs)
        admin_cov = sum(len(s.text) for s in loc_segs if s.seg_type in _ADDR_TYPES) / n
        location_cov = sum(len(s.text) for s in loc_segs
                           if s.seg_type in (SegType.LOCATION, SegType.ORIENTATION)) / n
        f["loc_admin_cov"] = admin_cov
        f["loc_geo_cov"] = admin_cov + location_cov
        f["loc_n_province"] = sum(1 for s in loc_segs if s.seg_type == SegType.PROVINCE)
        f["loc_n_city"] = sum(1 for s in loc_segs if s.seg_type == SegType.CITY)
        f["loc_n_district"] = sum(1 for s in loc_segs if s.seg_type == SegType.DISTRICT)
        f["loc_n_town"] = sum(1 for s in loc_segs if s.seg_type == SegType.TOWN)
        f["loc_n_village"] = sum(1 for s in loc_segs if s.seg_type == SegType.VILLAGE)
        f["loc_n_community"] = sum(1 for s in loc_segs if s.seg_type == SegType.COMMUNITY)
        f["loc_n_road"] = sum(1 for s in loc_segs if s.seg_type == SegType.ROAD)
        f["loc_road_cov"] = sum(len(s.text) for s in loc_segs
                                if s.seg_type == SegType.ROAD) / n
        f["loc_has_location"] = float(any(s.seg_type == SegType.LOCATION for s in loc_segs))
        f["loc_has_orientation"] = float(any(s.seg_type == SegType.ORIENTATION for s in loc_segs))

        org_segs = org_res.segments
        org_last = org_segs[-1] if org_segs else None
        f["org_n_segs"] = len(org_segs)
        f["org_n_brand"] = sum(1 for s in org_segs if s.seg_type == SegType.BRAND)
        f["org_n_industry"] = sum(1 for s in org_segs if s.seg_type == SegType.INDUSTRY)
        f["org_brand_cov"] = sum(len(s.text) for s in org_segs
                                 if s.seg_type == SegType.BRAND) / n
        f["org_has_poi_terminal"] = float(
            org_last is not None and org_last.seg_type == SegType.ORG_SUFFIX)
        f["org_last_is_brand"] = float(
            org_last is not None and org_last.seg_type == SegType.BRAND)
        f["org_last_is_industry"] = float(
            org_last is not None and org_last.seg_type == SegType.INDUSTRY)
        f["has_comp"] = float(has_comp)
        f["has_industry"] = float(f["org_n_industry"] > 0)

        d4 = self._d4_info(org_segs, SegType.ORG_SUFFIX)
        f["has_gov"] = float(bool(org_last and any(
            org_last.text.endswith(g) for g in GOV_SUFFIXES)))
        f["double_negative"] = float(self._double_negative(d4)) if d4 else 0.0
        self._fill_d4_feats(f, "d4", d4)

        sfx_aff = self.idx.lookup_suffix(d4) if d4 else None
        f["sfx_aff_org_ratio"] = sfx_aff.org_ratio if sfx_aff else np.nan
        f["sfx_aff_loc_ratio"] = sfx_aff.loc_ratio if sfx_aff else np.nan

        d3_text = "".join(s.text for s in org_segs if s.seg_type == SegType.INDUSTRY) or None
        trd_aff = self.idx.lookup_trade(d3_text) if d3_text else None
        f["trd_aff_org_ratio"] = trd_aff.org_ratio if trd_aff else np.nan
        f["trd_aff_loc_ratio"] = trd_aff.loc_ratio if trd_aff else np.nan

        brand_text = "".join(s.text for s in org_segs if s.seg_type == SegType.BRAND)
        f["org_brand_score"] = self.pipe.org.brand_score(brand_text) if brand_text else np.nan

        d1_prefix = ""
        for s in loc_segs:
            if s.seg_type in _ADDR_TYPES:
                d1_prefix += s.text
            else:
                break
        addr_aff = self.idx.lookup_addr(d1_prefix) if d1_prefix else None
        f["addr_aff_org_ratio"] = addr_aff.org_ratio if addr_aff else np.nan
        f["addr_aff_loc_ratio"] = addr_aff.loc_ratio if addr_aff else np.nan
        f["d1_prefix_len"] = len(d1_prefix)

        poi_segs = poi_res.segments if poi_res else []
        poi_last = poi_segs[-1] if poi_segs else None
        f["poi_n_segs"] = len(poi_segs)
        f["poi_n_brand"] = sum(1 for s in poi_segs if s.seg_type == SegType.BRAND)
        f["poi_n_industry"] = sum(1 for s in poi_segs if s.seg_type == SegType.INDUSTRY)
        f["poi_brand_cov"] = sum(len(s.text) for s in poi_segs
                                 if s.seg_type == SegType.BRAND) / n
        f["poi_has_poi_terminal"] = float(
            poi_last is not None and poi_last.seg_type == SegType.POI)
        f["poi_last_is_brand"] = float(
            poi_last is not None and poi_last.seg_type == SegType.BRAND)
        f["poi_last_is_industry"] = float(
            poi_last is not None and poi_last.seg_type == SegType.INDUSTRY)

        poi_d4 = self._d4_info(poi_segs, SegType.POI) if poi_res else None
        self._fill_d4_feats(f, "poi_d4", poi_d4)
        poi_sfx_aff = self.idx.lookup_suffix(poi_d4) if poi_d4 else None
        f["poi_sfx_aff_org_ratio"] = poi_sfx_aff.org_ratio if poi_sfx_aff else np.nan
        f["poi_sfx_aff_loc_ratio"] = poi_sfx_aff.loc_ratio if poi_sfx_aff else np.nan

        poi_brand_text = "".join(s.text for s in poi_segs if s.seg_type == SegType.BRAND)
        if has_comp:
            f["poi_brand_score"] = np.nan
        else:
            f["poi_brand_score"] = (
                self.pipe.org.brand_score(poi_brand_text) if poi_brand_text else np.nan)

        return f, loc_res, org_res, poi_res

    def extract(self, text):
        """兼容旧接口: 提取特征并缓存本次段结果到 last_results。

        仅供单线程/预计算使用; 并发推理请使用 extract_with_results,
        避免共享 last_results 造成请求间串扰。
        """
        f, loc_res, org_res, poi_res = self.extract_with_results(text)
        self.last_results = (loc_res, org_res, poi_res)
        return f

    def extract_vector(self, text):
        f = self.extract(text)
        return [f.get(name, np.nan) for name in FEATURE_NAMES]
