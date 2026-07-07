"""dict_ner 统一识别总线 — 地名/机构名/POI/品牌"""
import os
import warnings
import threading

COMPANY_SUFFIXES = {
    "公司", "有限公司", "有限责任公司", "股份有限公司",
    "集团", "企业", "总公司", "分公司", "子公司",
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DICT_DIR = os.path.join(BASE_DIR, "dicts")


class DictNerPipeline:
    def __init__(self, loc_dict: str = "loc_v1.1.2",
                 org_dict: str = "v1.1.2",
                 poi_dict: str = "poi_v1.1.2"):
        self.loc_version = loc_dict
        self.org_version = org_dict
        self.poi_version = poi_dict
        self._loc = None
        self._org = None
        self._poi = None
        self._lock = threading.Lock()

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
                    self._brand = BrandModel(DICT_DIR, version="v1.1.2")
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
