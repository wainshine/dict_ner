"""统一 DP 引擎 — Trie + Viterbi, LOC/ORG/POI 差异全部配置化

行为保持: 与 loc/recognizer.py + org/recognizer.py 输出逐段一致 (gate.py 门禁)。
"""
import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from core.types import (
    SegType, AddressSegment, AddressResult,
    LEVEL_ORDER, ADMIN_SUFFIX_MAP, LOCATION_SUFFIX_SET, POI_SUFFIX_MAP,
)
from loc.importer import classify_suffix

STOP_CHARS = frozenset("，。；、！？：,.!?;: \t\r\n　 ")
_SEPARATOR_CHARS = "，。；、！？：,.!?;: \t\r\n　 "

TRAILING_SINGLE = {"店", "厂", "站", "路", "村", "屯", "镇", "乡", "街",
                   "馆", "铺", "坊", "档", "摊", "所", "局", "处", "阁",
                   "苑", "城", "园", "庭", "屋", "舍", "汇", "行", "场"}


def build_trie(entries):
    trie = {}
    all_words = set()
    type_counts = {}
    for word, seg_type, freq in entries:
        all_words.add(word)
        node = trie
        for ch in word:
            node = node.setdefault(ch, {})
        cur = node.get("#")
        if cur is None:
            node["#"] = (seg_type, freq)
        else:
            cur_type, cur_freq = cur
            new_prio = LEVEL_ORDER.get(seg_type, 99)
            old_prio = LEVEL_ORDER.get(cur_type, 99)
            if new_prio < old_prio or (new_prio == old_prio and freq > cur_freq):
                node["#"] = (seg_type, freq)
        type_counts[seg_type] = type_counts.get(seg_type, 0) + 1
    return trie, all_words, type_counts


@dataclass
class EngineConfig:
    name: str
    entries: List[Tuple[str, SegType, int]]
    trans_table: Dict[Tuple[SegType, SegType], float]
    start_costs: Dict[SegType, float]
    word_cost_mode: str
    single_char_cost: float
    single_char_type: SegType
    short_d4_penalty: bool = False
    use_admin_patterns: bool = False
    use_location_patterns: bool = False
    post_hooks: Tuple[str, ...] = ()

    def type_counts_override(self):
        return None


class DPEngine:
    def __init__(self, config: EngineConfig):
        self.config = config
        self.trie, self.all_words, type_counts = build_trie(config.entries)
        self.total_freq = {t: max(1, c) for t, c in type_counts.items()}

    def _transition_cost(self, from_type, to_type):
        if from_type is None:
            return self.config.start_costs.get(to_type, 5.0)
        return self.config.trans_table.get((from_type, to_type), 5.0)

    def _word_cost(self, seg_type, freq, length):
        if freq == 0:
            if self.config.word_cost_mode == "loc":
                if seg_type == SegType.LOCATION:
                    if length <= 2:
                        return 1.5
                    elif length <= 4:
                        return 2.0
                    else:
                        return 2.5
                if length <= 1:
                    return 4.0
                elif length <= 2:
                    return 3.0
                elif length <= 4:
                    return 2.5
                elif length <= 10:
                    return 2.0
                else:
                    return 2.0 + (length - 10) * 0.2
            else:
                if length <= 2:
                    return 2.0
                elif length <= 4:
                    return 2.5
                elif length <= 8:
                    return 3.0
                else:
                    return 4.0

        total = self.total_freq.get(seg_type, 1)
        if total <= 0:
            total = 1
        idf = -math.log((freq + 1) / (total + 1))
        if length <= 1:
            lp = 1.5
        elif length <= 2:
            lp = 0.5
        elif length <= 8:
            lp = 0.0
        else:
            lp = (length - 8) * 0.3
        return max(0.5, idf + lp + 1.0)

    def _find_trie_matches(self, text, n):
        matches = []
        trie = self.trie
        for i in range(n):
            ch = text[i]
            if ch not in trie:
                continue
            node = trie[ch]
            j = i + 1
            if "#" in node:
                stype, freq = node["#"]
                matches.append((i, j, stype, freq))
            while j < n:
                ch = text[j]
                if ch not in node:
                    break
                node = node[ch]
                j += 1
                if "#" in node:
                    stype, freq = node["#"]
                    matches.append((i, j, stype, freq))
        return matches

    def _find_admin_patterns(self, text, n):
        suffix_positions = []
        for seg_type, suffixes in ADMIN_SUFFIX_MAP.items():
            for sfx in suffixes:
                pos = text.find(sfx)
                while pos >= 0:
                    end = pos + len(sfx)
                    suffix_positions.append((end, pos, sfx, seg_type))
                    pos = text.find(sfx, end)
        for sfx in POI_SUFFIX_MAP:
            pos = text.find(sfx)
            while pos >= 0:
                end = pos + len(sfx)
                suffix_positions.append((end, pos, sfx, SegType.POI))
                pos = text.find(sfx, end)
        if not suffix_positions:
            return []

        TYPE_PRIORITY = {
            SegType.PROVINCE: 0, SegType.CITY: 1, SegType.DISTRICT: 2,
            SegType.TOWN: 3, SegType.VILLAGE: 4, SegType.COMMUNITY: 5,
            SegType.ROAD: 6, SegType.POI: 7, SegType.LOCATION: 8,
        }
        suffix_positions.sort(key=lambda x: (x[0], -len(x[2]), TYPE_PRIORITY.get(x[3], 9)))

        merged = []
        for end, spos, sfx, stype in suffix_positions:
            if not merged:
                merged.append((end, spos, sfx, stype))
                continue
            prev_end, prev_spos, prev_sfx, prev_type = merged[-1]
            if end <= prev_end or spos < prev_end:
                if len(sfx) > len(prev_sfx):
                    merged[-1] = (end, spos, sfx, stype)
                continue
            merged.append((end, spos, sfx, stype))

        matches = []
        last_boundary = 0
        for end, spos, sfx, stype in merged:
            word = text[last_boundary:end]
            stripped = word.lstrip(_SEPARATOR_CHARS)
            if len(stripped) > 1 and len(stripped) >= len(sfx):
                if stripped not in self.all_words:
                    match_start = end - len(stripped)
                    matches.append((match_start, end, stype, 0))
            last_boundary = end
        return matches

    def _find_location_patterns(self, text, n):
        matches = []
        for sfx in LOCATION_SUFFIX_SET:
            pos = text.find(sfx)
            while pos >= 0:
                end = pos + len(sfx)
                matches.append((pos, end, SegType.LOCATION, 0))
                pos = text.find(sfx, end)
        return matches

    def recognize(self, text):
        raw_text = text
        text = text.strip()
        if not text:
            return AddressResult(original=raw_text)

        n = len(text)
        matches = self._find_trie_matches(text, n)
        if self.config.use_admin_patterns:
            matches.extend(self._find_admin_patterns(text, n))
        if self.config.use_location_patterns:
            matches.extend(self._find_location_patterns(text, n))

        by_start = {}
        for s, e, stype, freq in matches:
            by_start.setdefault(s, []).append((s, e, stype, freq))

        char_type = self.config.single_char_type
        dp = [(float("inf"), -1, None, 0.0, "") for _ in range(n + 1)]
        dp[0] = (0.0, -1, None, 0.0, "")

        for i in range(n):
            if dp[i][0] >= float("inf") * 0.5:
                continue
            prev_type = dp[i][2]

            for start, end, seg_type, freq in by_start.get(i, []):
                wc = self._word_cost(seg_type, freq, end - start)
                if (self.config.short_d4_penalty and seg_type == SegType.POI
                        and 2 <= (end - start) <= 3 and freq < 50000
                        and end < n * 0.8):
                    wc = max(wc, 7.0)
                tc = self._transition_cost(prev_type, seg_type)
                total = dp[i][0] + wc + tc
                if total < dp[end][0]:
                    dp[end] = (total, i, seg_type, freq, text[start:end])

            scc = self.config.single_char_cost
            tc = self._transition_cost(prev_type, char_type)
            total = dp[i][0] + scc + tc
            if total < dp[i + 1][0]:
                dp[i + 1] = (total, i, char_type, 0.0, text[i])

        segments = self._backtrack(dp, text, n)
        for hook in self.config.post_hooks:
            segments = getattr(self, f"_post_{hook}")(segments)
        return AddressResult(original=raw_text, segments=segments)

    def _backtrack(self, dp, text, n):
        segments = []
        pos = n
        is_loc = self.config.single_char_type == SegType.CHAR
        while pos > 0:
            cost, prev, seg_type, freq, word = dp[pos]
            if pos == prev:
                break
            if seg_type != SegType.CHAR:
                segment_cost = cost - dp[prev][0]
                if not is_loc:
                    segment_cost = max(segment_cost, 0.01)
                segments.append(AddressSegment(
                    text=word, seg_type=seg_type, start=prev, end=pos,
                    confidence=1.0 / (1.0 + segment_cost),
                ))
            else:
                ch = text[prev:pos]
                if ch in STOP_CHARS:
                    pos = prev
                    continue
                segments.append(AddressSegment(
                    text=ch, seg_type=SegType.UNKNOWN, start=prev, end=pos,
                    confidence=0.3,
                ))
            pos = prev
        segments.reverse()
        return segments

    def _post_assign_poi_types(self, segments):
        for s in segments:
            if s.seg_type == SegType.POI:
                s.poi_type = classify_suffix(s.text)
        return segments

    def _post_assign_poi_types_loc(self, segments):
        for s in segments:
            if s.seg_type in (SegType.POI, SegType.POI_SUB):
                s.poi_type = self._detect_poi_type(s.text)
        return segments

    def _detect_poi_type(self, text):
        from loc.importer import _SAFE_SINGLE_SUFFIXES
        for sfx, cat in sorted(POI_SUFFIX_MAP.items(), key=lambda x: -len(x[0])):
            if len(sfx) == 1:
                if sfx in _SAFE_SINGLE_SUFFIXES and len(text) <= 3 and text.endswith(sfx):
                    return cat
            elif text.endswith(sfx):
                return cat
        return classify_suffix(text)

    def _post_adjudicate_town(self, segments):
        admin_sfx = ("镇", "乡", "街道", "办事处", "苏木", "民族乡")
        merge_hint = ("镇", "乡", "村", "嘎查")
        gov_hint = ("人民政府", "委员会", "村委会", "居委会", "办事处")
        for i, s in enumerate(segments):
            if s.seg_type != SegType.TOWN:
                continue
            if s.text.endswith(admin_sfx):
                continue
            if i == 0:
                continue
            nxt = segments[i + 1] if i + 1 < len(segments) else None
            if (nxt is not None and nxt.seg_type in (SegType.BRAND, SegType.UNKNOWN)
                    and nxt.text in merge_hint):
                continue
            rest = segments[i + 1:]
            if any(g in "".join(l.text for l in rest) for g in gov_hint):
                continue
            if any(l.seg_type in (SegType.INDUSTRY, SegType.POI) for l in rest):
                s.seg_type = SegType.BRAND
        return segments

    def _post_merge_unknown(self, segments):
        merged = []
        for s in segments:
            if (merged and s.seg_type == SegType.UNKNOWN
                    and merged[-1].seg_type == SegType.UNKNOWN):
                merged[-1].text += s.text
                merged[-1].end = s.end
            else:
                merged.append(s)
        return merged

    def _post_leading_bracket(self, segments):
        i = 0
        while i < len(segments) - 1:
            cur, nxt = segments[i], segments[i + 1]
            if (cur.seg_type in (SegType.UNKNOWN, SegType.BRAND)
                    and len(cur.text) == 1 and cur.text in "（("
                    and nxt.seg_type == SegType.POI):
                nxt.text = cur.text + nxt.text
                nxt.start = cur.start
                segments.pop(i)
                continue
            i += 1
        return segments

    def _post_trailing_single(self, segments):
        if len(segments) >= 2:
            last = segments[-1]
            prev = segments[-2]
            if (last.seg_type == SegType.UNKNOWN and len(last.text) == 1
                    and prev.seg_type in (SegType.INDUSTRY, SegType.POI, SegType.ROAD)):
                if last.text in TRAILING_SINGLE or prev.seg_type == SegType.POI:
                    prev.text += last.text
                    prev.end = last.end
                    prev.seg_type = SegType.POI
                    prev.poi_type = classify_suffix(prev.text)
                    segments.pop()
        return segments

    def _post_relabel_brand(self, segments):
        for s in segments:
            if s.seg_type == SegType.UNKNOWN:
                s.seg_type = SegType.BRAND
        return segments

    def _post_merge_orientation(self, segments):
        if not segments:
            return segments
        result = []
        i = 0
        while i < len(segments):
            seg = segments[i]
            if seg.seg_type == SegType.ORIENTATION and i + 1 < len(segments):
                nxt = segments[i + 1]
                if nxt.seg_type in (SegType.ROAD, SegType.POI, SegType.TOWN,
                                    SegType.LOCATION, SegType.UNKNOWN):
                    result.append(AddressSegment(
                        text=seg.text + nxt.text,
                        seg_type=nxt.seg_type,
                        start=seg.start, end=nxt.end,
                        confidence=(seg.confidence + nxt.confidence) / 2,
                    ))
                    i += 2
                    continue
            result.append(seg)
            i += 1
        return result

    def _post_merge_location(self, segments):
        if not segments:
            return segments
        result = []
        for seg in segments:
            if (seg.seg_type == SegType.LOCATION and result
                    and result[-1].seg_type in (SegType.ROAD, SegType.POI,
                                                SegType.TOWN, SegType.UNKNOWN)):
                result[-1].text += seg.text
                result[-1].end = seg.end
            else:
                result.append(seg)
        return result

    def _post_strip_road_conjunction(self, segments):
        result = []
        for i, seg in enumerate(segments):
            if (seg.seg_type == SegType.ROAD and len(seg.text) > 2
                    and seg.text[0] in "与和"):
                result.append(AddressSegment(
                    text=seg.text[0], seg_type=SegType.UNKNOWN,
                    start=seg.start, end=seg.start + 1,
                    confidence=seg.confidence))
                result.append(AddressSegment(
                    text=seg.text[1:], seg_type=SegType.ROAD,
                    start=seg.start + 1, end=seg.end,
                    confidence=seg.confidence))
            else:
                result.append(seg)
        return result

    def _post_merge_same_type(self, segments):
        if not segments:
            return segments
        result = []
        for seg in segments:
            if result and seg.seg_type == result[-1].seg_type:
                if seg.seg_type in (SegType.POI, SegType.POI_SUB, SegType.LOCATION,
                                    SegType.CHAR, SegType.UNKNOWN, SegType.NUMERIC):
                    result[-1].text += seg.text
                    result[-1].end = seg.end
                    continue
            result.append(seg)
        return result
