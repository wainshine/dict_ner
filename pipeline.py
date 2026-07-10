"""dict_ner 统一识别总线 — 地名/机构名/POI/品牌"""
import csv
import os
import pickle
import warnings
import threading

from core.types import SegType

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

_ADDR_TYPES = {
    SegType.PROVINCE, SegType.CITY, SegType.DISTRICT,
    SegType.TOWN, SegType.VILLAGE, SegType.COMMUNITY, SegType.ROAD,
}

_GEO_SEG_TYPES = {
    SegType.PROVINCE, SegType.CITY, SegType.DISTRICT,
    SegType.TOWN, SegType.VILLAGE, SegType.COMMUNITY,
    SegType.ROAD, SegType.LOCATION, SegType.ORIENTATION,
}

_ORG_TYPE_REMAP = {"POI": "ORG_SUFFIX"}

CATEGORY_LABELS = ("ORG", "POI", "ADDR", "UNKNOWN")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DICT_DIR = os.path.join(BASE_DIR, "dicts")


class DictNerPipeline:
    def __init__(self, loc_dict: str = "loc_v1.2.1",
                 org_dict: str = "v1.2.1",
                 poi_dict: str = "poi_v1.2.1",
                 t_unknown: float = 0.10):
        self.loc_version = loc_dict
        self.org_version = org_dict
        self.poi_version = poi_dict
        self._loc = None
        self._org = None
        self._poi = None
        self._lock = threading.Lock()
        self.T_UNKNOWN = t_unknown
        self._d4_map = None
        self._suffix_table = None
        self._sql_suffixes = None

    @property
    def loc(self):
        if self._loc is None:
            with self._lock:
                if self._loc is None:
                    from loc.builder import DictBuilder
                    from loc.recognizer import AddressRecognizer
                    b = DictBuilder.load(DICT_DIR, self.loc_version)
                    self._loc = AddressRecognizer(b.dict_data)
        return self._loc

    @property
    def org(self):
        if self._org is None:
            with self._lock:
                if self._org is None:
                    from org.recognizer import OrgDPRecognizer
                    self._org = OrgDPRecognizer(DATA_DIR, version=self.org_version)
        return self._org

    @property
    def poi(self):
        if self._poi is None:
            with self._lock:
                if self._poi is None:
                    from poi.recognizer import PoiRecognizer
                    self._poi = PoiRecognizer(DATA_DIR, dict_name=f"{self.poi_version}.pkl")
        return self._poi

    @property
    def brand(self):
        """Brand model — loaded but not yet called in recognition pipeline (dormant, awaiting v1.3)."""
        if not hasattr(self, '_brand'):
            with self._lock:
                if not hasattr(self, '_brand'):
                    from brand.model import BrandModel
                    self._brand = BrandModel(DICT_DIR, version="v1.2.1")
                    if not self._brand.load():
                        warnings.warn("Brand model not loaded, brand_score will return 0.5")
        return self._brand

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
        return self._sql_suffixes

    def _has_company_suffix(self, org_result):
        for s in org_result.segments:
            for sfx in COMPANY_SUFFIXES:
                if s.text.endswith(sfx):
                    return True
        return False

    def recognize(self, text: str):
        text = text.strip()
        loc_result = self.loc.recognize(text)
        org_result = self.org.recognize(text)

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

    def classify(self, text: str) -> dict:
        text = text.strip()
        if not text:
            return {"text": "", "category": "UNKNOWN", "confidence": 1.0,
                    "best": None, "all": None}
        loc_res = self.loc.recognize(text)
        org_res = self.org.recognize(text)
        has_comp = self._has_company_suffix(org_res)
        poi_res = None if has_comp else self.poi.recognize(text)
        feats = self._extract_features(text, loc_res, org_res, poi_res, has_comp)
        scores = self._score(feats)
        category, confidence = self._decide(feats, scores)
        best = self._select_best(category, loc_res, org_res, poi_res)
        return {
            "text": text,
            "category": category,
            "confidence": round(confidence, 4),
            "best": best,
            "all": {
                "loc": loc_res.to_dict(),
                "org": org_res.to_dict(),
                "poi": poi_res.to_dict() if poi_res else None,
            },
        }

    def classify_batch(self, texts) -> list:
        return [self.classify(t) for t in texts]

    def _extract_features(self, text, loc_res, org_res, poi_res, has_comp):
        from core.csv_index import CsvIndex
        idx = CsvIndex.instance()

        org_segs = org_res.segments
        org_last = org_segs[-1] if org_segs else None
        d4_suffix = org_last.text if (org_last and org_last.seg_type == SegType.POI) else None
        if d4_suffix is None and org_last:
            org_text = org_last.text
            cat = self._lookup_d4_category(org_text)
            if cat is not None and cat not in ("AMBIGUOUS", "UNKNOWN"):
                d4_suffix = org_text
            elif self._lookup_suffix_category(org_text) is not None:
                d4_suffix = org_text
        has_gov = False
        if org_last and d4_suffix:
            has_gov = any(org_last.text.endswith(g) for g in GOV_SUFFIXES)
        has_industry = any(s.seg_type == SegType.INDUSTRY for s in org_segs)

        poi_segs = poi_res.segments if poi_res else []
        poi_last = poi_segs[-1] if poi_segs else None
        poi_d4 = poi_last.text if (poi_last and poi_last.seg_type == SegType.POI) else None
        if poi_d4 is None and poi_last:
            poi_text = poi_last.text
            cat = self._lookup_d4_category(poi_text)
            if cat is not None and cat not in ("AMBIGUOUS", "UNKNOWN"):
                poi_d4 = poi_text
            elif self._lookup_suffix_category(poi_text) is not None:
                poi_d4 = poi_text

        n = max(1, len(text))
        admin_cov = sum(len(s.text) for s in loc_res.segments
                        if s.seg_type in _ADDR_TYPES) / n
        location_cov = sum(len(s.text) for s in loc_res.segments
                           if s.seg_type in (SegType.LOCATION, SegType.ORIENTATION)) / n
        geo_cov = admin_cov + location_cov

        d1_prefix = ""
        for s in loc_res.segments:
            if s.seg_type in _ADDR_TYPES:
                d1_prefix += s.text
            else:
                break
        d1_prefix = d1_prefix or None

        d3_text = "".join(s.text for s in org_segs
                          if s.seg_type == SegType.INDUSTRY) or None

        sfx_aff = idx.lookup_suffix(d4_suffix) if d4_suffix else None
        trd_aff = idx.lookup_trade(d3_text) if d3_text else None
        addr_aff = idx.lookup_addr(d1_prefix) if d1_prefix else None
        poi_sfx_aff = idx.lookup_suffix(poi_d4) if poi_d4 else None

        has_geo = any(s.seg_type in _GEO_SEG_TYPES for s in loc_res.segments)

        return {
            "n": n, "has_comp": has_comp, "has_gov": has_gov,
            "d4_suffix": d4_suffix, "d3_text": d3_text, "d1_prefix": d1_prefix,
            "poi_d4": poi_d4, "has_industry": has_industry, "has_geo": has_geo,
            "org_has_poi_terminal": org_last is not None and org_last.seg_type == SegType.POI,
            "poi_has_poi_terminal": poi_last is not None and poi_last.seg_type == SegType.POI,
            "admin_cov": admin_cov, "geo_cov": geo_cov,
            "sfx_aff": sfx_aff, "trd_aff": trd_aff,
            "addr_aff": addr_aff, "poi_sfx_aff": poi_sfx_aff,
        }

    def _score(self, f):
        sfx_org_r = f["sfx_aff"].org_ratio if f["sfx_aff"] else 0.0
        trd_org_r = f["trd_aff"].org_ratio if f["trd_aff"] else 0.0
        if f["has_comp"] or f["has_gov"]:
            org_score = 0.90 + 0.08 * (f["has_industry"] or trd_org_r > 0.5)
        elif sfx_org_r > 0.6:
            org_score = sfx_org_r * 0.80
        else:
            org_score = sfx_org_r * 0.30
        org_score = min(org_score, 0.98)

        if f["poi_d4"] is None:
            poi_score = 0.0
        else:
            loc_r = f["poi_sfx_aff"].loc_ratio if f["poi_sfx_aff"] else 0.2
            poi_base = loc_r * 0.75
            if poi_base < 0.15:
                poi_base = 0.15
            poi_score = min(poi_base, 0.90)

        addr_score = f["geo_cov"] * 0.50
        if f["addr_aff"] and f["addr_aff"].loc_ratio > 0.5:
            addr_score += f["geo_cov"] * 0.25
        if (f["has_comp"] or f["has_gov"]) or org_score > 0.45:
            addr_score *= 0.25
        addr_score = min(addr_score, 1.0)

        return {"ORG": org_score, "POI": poi_score, "ADDR": addr_score}

    def _lookup_d4_category(self, d4):
        entry = self.d4_map.get(d4)
        if entry:
            return entry.get("category", "UNKNOWN")
        return None

    def _lookup_suffix_category(self, d4):
        if not d4 or not self.suffix_table:
            return None
        for end in range(len(d4), 0, -1):
            for start in range(0, end):
                w = d4[start:end]
                if w in self.suffix_table:
                    return self.suffix_table[w]
        return None

    def _double_negative(self, d4, idx):
        if not d4 or len(d4) < 2:
            return False
        for slen in range(min(4, len(d4) - 1), 1, -1):
            sfx_candidate = d4[-slen:]
            prefix = d4[:-slen]
            if prefix and d4 not in idx.suffix and prefix not in idx.trade:
                return True
        return False

    def _decide(self, f, scores):
        scores = dict(scores)
        from core.csv_index import CsvIndex
        idx = CsvIndex.instance()

        if (f["has_comp"] or f["has_gov"]) and f["org_has_poi_terminal"]:
            return "ORG", scores["ORG"]

        d4 = f.get("d4_suffix")
        if d4:
            if d4 not in self.sql_suffixes:
                return "POI", max(scores["POI"], 0.70)

            cat = self._lookup_d4_category(d4)
            if cat == "POI_FAC":
                return "POI", max(scores["POI"], 0.75)
            elif cat == "POI_STORE":
                if f["has_geo"] or self._double_negative(d4, idx):
                    return "POI", max(scores["POI"], 0.75)
            elif cat == "ORG":
                scores["ORG"] = min(max(scores["ORG"], 0.80), 0.98)

            if cat in (None, "AMBIGUOUS", "UNKNOWN"):
                cat_sfx = self._lookup_suffix_category(d4)
                if cat_sfx == "POI_FAC":
                    return "POI", max(scores["POI"], 0.75)
                elif cat_sfx == "POI_STORE":
                    if f["has_geo"] or self._double_negative(d4, idx):
                        return "POI", max(scores["POI"], 0.75)
                elif cat_sfx == "ORG":
                    scores["ORG"] = min(max(scores["ORG"], 0.80), 0.98)

        best_cat = max(scores, key=scores.get)
        best_val = scores[best_cat]
        if best_val < self.T_UNKNOWN:
            return "UNKNOWN", best_val
        return best_cat, best_val

    def _select_best(self, category, loc_res, org_res, poi_res):
        if category == "ORG":
            d = org_res.to_dict()
            for s in d["segments"]:
                s["type"] = _ORG_TYPE_REMAP.get(s["type"], s["type"])
            return d
        elif category == "POI":
            return poi_res.to_dict() if poi_res else None
        elif category == "ADDR":
            return loc_res.to_dict()
        return None
