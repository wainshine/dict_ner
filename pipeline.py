"""dict_ner 统一识别总线 — 地名/机构名/POI/品牌"""
import os
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
}

POI_FACILITY_SUFFIXES = {
    "停车场", "停车库", "公厕", "厕所",
    "收费站", "加油站", "加气站",
    "公交站", "地铁站", "客运站", "火车站",
    "码头", "港口", "渡口",
}

POI_STORE_SUFFIXES = {
    "店", "超市", "便利店", "商店", "商场", "市场", "菜场",
    "餐厅", "饭店", "食堂",
    "酒店", "宾馆", "旅馆", "招待所",
    "网吧", "会所", "健身房", "影院", "电影院",
    "馆", "行", "房", "厅", "部", "庄", "阁", "楼", "城", "吧",
    "场", "社", "亭", "家", "坊", "斋", "居", "府", "轩",
}

POI_SUFFIX_OVERRIDES = {
    "小吃", "快餐", "麻辣烫", "烧烤", "火锅", "私房菜",
    "商行", "车行", "专卖", "专柜", "批发", "批发部", "经营部",
    "手机卖场", "报刊亭", "百货",
    "造型", "汽修", "美发", "快递", "发艺", "KTV",
    "布艺", "窗帘", "童装", "家纺", "灯饰",
    "生活馆", "体验馆", "蛋糕房", "彩票",
    "客栈", "总代理", "总经销", "美容院", "发屋", "浴池",
    "美甲美睫", "批发零售", "儿童乐园", "小屋", "住宿",
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
    def __init__(self, loc_dict: str = "loc_v1.2.0",
                 org_dict: str = "v1.2.0",
                 poi_dict: str = "poi_v1.2.0",
                 t_unknown: float = 0.15):
        self.loc_version = loc_dict
        self.org_version = org_dict
        self.poi_version = poi_dict
        self._loc = None
        self._org = None
        self._poi = None
        self._lock = threading.Lock()
        self.T_UNKNOWN = t_unknown

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
                    self._brand = BrandModel(DICT_DIR, version="v1.2.0")
                    if not self._brand.load():
                        warnings.warn("Brand model not loaded, brand_score will return 0.5")
        return self._brand

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
            check_suffixes = POI_FACILITY_SUFFIXES | POI_STORE_SUFFIXES
            if any(org_text.endswith(s) for s in check_suffixes) or org_text in POI_SUFFIX_OVERRIDES:
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
            check_suffixes = POI_FACILITY_SUFFIXES | POI_STORE_SUFFIXES
            if any(poi_text.endswith(s) for s in check_suffixes) or poi_text in POI_SUFFIX_OVERRIDES:
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
            store_match = any(f["poi_d4"].endswith(s) for s in POI_STORE_SUFFIXES)
            has_facility = any(f["poi_d4"].endswith(s) for s in POI_FACILITY_SUFFIXES)
            is_override = f["poi_d4"] in POI_SUFFIX_OVERRIDES
            poi_base = loc_r * 0.75
            if poi_base < 0.15 and not has_facility:
                poi_base = 0.15
            if is_override:
                poi_base = max(poi_base, 0.55)
            poi_score = poi_base + 0.20 * store_match + 0.25 * has_facility
            poi_score = min(poi_score, 0.90)

        addr_score = f["geo_cov"] * 0.50
        if f["addr_aff"] and f["addr_aff"].loc_ratio > 0.5:
            addr_score += f["geo_cov"] * 0.25
        if (f["has_comp"] or f["has_gov"]) or org_score > 0.45:
            addr_score *= 0.25
        addr_score = min(addr_score, 1.0)

        return {"ORG": org_score, "POI": poi_score, "ADDR": addr_score}

    def _decide(self, f, scores):
        if (f["has_comp"] or f["has_gov"]) and f["org_has_poi_terminal"]:
            return "ORG", scores["ORG"]

        d4 = f.get("d4_suffix")
        if d4:
            d4_clean = d4.rstrip(")")
            if d4_clean in POI_SUFFIX_OVERRIDES:
                if not (f["has_comp"] or f["has_gov"]):
                    return "POI", max(scores["POI"], 0.70)

            if any(d4.endswith(s) for s in POI_FACILITY_SUFFIXES) or any(d4.rstrip(")").endswith(s) for s in POI_FACILITY_SUFFIXES):
                return "POI", max(scores["POI"], 0.75)

            if any(d4.endswith(s) for s in POI_STORE_SUFFIXES) or any(d4_clean.endswith(s) for s in POI_STORE_SUFFIXES):
                if f["has_geo"]:
                    return "POI", max(scores["POI"], 0.75)
                from core.csv_index import CsvIndex
                idx = CsvIndex.instance()
                match_d4 = d4_clean if d4_clean != d4 else d4
                store_sfx = max((s for s in POI_STORE_SUFFIXES if match_d4.endswith(s)), key=len)
                prefix = match_d4[:-len(store_sfx)] if len(match_d4) > len(store_sfx) else ""
                if prefix and match_d4 not in idx.suffix and prefix not in idx.trade:
                    return "POI", max(scores["POI"], 0.70)
                if not (f["has_comp"] or f["has_gov"]):
                    return "POI", max(scores["POI"], 0.65)

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
