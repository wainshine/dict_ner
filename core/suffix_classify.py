"""POI 后缀分类 — v2/v3 共享（V1.1 从 loc/importer.py 提取）"""

from core.types import POI_SUFFIX_MAP


_SAFE_SINGLE_SUFFIXES = {"厂", "店", "站", "园", "局", "院"}


def classify_suffix(sfx: str) -> str:
    for kw, cat in sorted(POI_SUFFIX_MAP.items(), key=lambda x: -len(x[0])):
        if len(kw) == 1:
            if kw in _SAFE_SINGLE_SUFFIXES and len(sfx) <= 3 and sfx.endswith(kw):
                return cat
        elif sfx.endswith(kw):
            return cat
    return "建筑"
