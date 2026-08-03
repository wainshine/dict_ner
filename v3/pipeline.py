"""v3 统一总线 — 新 DPEngine ×3 + 复用 v2 后处理与查表

段识别由 v3.engine 提供 (与旧识别器 20K 样本零差异, 见 engine/gate.py)。
复合机构检测/过度拆分合并/ORG_SUFFIX remap 复用 pipeline.py 逻辑。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import AddressResult, SegType
from pipeline import DictNerPipeline
from v3.engine.configs import build_loc_engine, build_org_engine, build_poi_engine

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
    def __init__(self, loc_dict="loc_v1.2.3", org_version="v1.2.3",
                 poi_dict="poi_v1.2.3.pkl"):
        from brand.model import BrandModel
        brand = BrandModel(DICT_DIR, version="v1.2.3")
        brand.load()
        self._loc_engine = build_loc_engine(loc_dict)
        self._poi_engine = build_poi_engine(poi_dict)
        self.org = _OrgAdapter(build_org_engine(org_version), brand)
        self._tables = DictNerPipeline()

    @property
    def loc(self):
        return self._loc_engine

    @property
    def poi(self):
        return self._poi_engine

    @property
    def d4_map(self):
        return self._tables.d4_map

    @property
    def suffix_table(self):
        return self._tables.suffix_table

    @property
    def sql_suffixes(self):
        return self._tables.sql_suffixes

    def _remap_org_segments(self, result):
        return self._tables._remap_org_segments(result)

    def _merge_over_split(self, segments):
        return self._tables._merge_over_split(segments)

    def _detect_compound(self, segments):
        return self._tables._detect_compound(segments)

    def _has_company_suffix(self, result):
        return self._tables._has_company_suffix(result)

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
