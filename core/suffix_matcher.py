"""共享后缀边界查找与合并逻辑"""
from typing import Dict, List, Set, Tuple
from core.types import SegType


def find_suffix_boundaries(text: str,
                           suffix_map: Dict[SegType, Set[str]]) -> List[Tuple[int, int, str, SegType]]:
    """Find all suffix boundaries in text, merge overlapping (keep longer suffix).

    Args:
        text: Input text to search.
        suffix_map: {SegType: {suffixes}} mapping.

    Returns:
        List of (end, start, suffix, seg_type) sorted by end position,
        with overlapping boundaries merged.
    """
    boundaries = []
    for seg_type, suffixes in suffix_map.items():
        for sfx in suffixes:
            pos = text.find(sfx)
            while pos >= 0:
                end = pos + len(sfx)
                boundaries.append((end, pos, sfx, seg_type))
                pos = text.find(sfx, end)

    if not boundaries:
        return []

    boundaries.sort(key=lambda x: (x[0], -len(x[2])))

    merged = []
    for end, start, sfx, stype in boundaries:
        if not merged:
            merged.append((end, start, sfx, stype))
            continue
        prev_end, prev_start, prev_sfx, prev_type = merged[-1]
        if end <= prev_end or start < prev_end:
            if len(sfx) > len(prev_sfx):
                merged[-1] = (end, start, sfx, stype)
            continue
        merged.append((end, start, sfx, stype))

    return merged
