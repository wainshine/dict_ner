import math
from typing import Dict, List, Optional, Tuple
from core.types import (
    SegType, AddressSegment, AddressResult,
    LEVEL_ORDER, ADMIN_SUFFIX_MAP, LOCATION_SUFFIX_MAP, POI_SUFFIX_MAP,
)
from core.suffix_matcher import find_suffix_boundaries


STOP_CHARS = set("，。；、！？：,.!?;: \t")


class AddressRecognizer:
    def __init__(self, dict_data: Dict[SegType, Dict[str, int]]):
        self.dict_data = dict_data
        self.trie = {}
        self.total_freq = {}
        self.all_words = set()
        self._build_trie()
        self._compute_total_freqs()
        self._build_transition_costs()

    def _build_trie(self):
        trie = {}
        all_words = set()
        for seg_type, word_freqs in self.dict_data.items():
            for word, freq in word_freqs.items():
                all_words.add(word)
                node = trie
                for ch in word:
                    node = node.setdefault(ch, {})
                current = node.get("#", None)
                if current is None or freq > current[1]:
                    node["#"] = (seg_type, freq)
        self.trie = trie
        self.all_words = all_words

    def _compute_total_freqs(self):
        for seg_type in self.dict_data:
            self.total_freq[seg_type] = max(1, len(self.dict_data[seg_type]))

    def _build_transition_costs(self):
        self.transition_cost = {}
        types = list(SegType)
        for i in range(len(types)):
            for j in range(len(types)):
                self.transition_cost[(types[i], types[j])] = 5.0

        valid = [
            (SegType.PROVINCE, SegType.CITY, 0.0),
            (SegType.PROVINCE, SegType.DISTRICT, 1.0),
            (SegType.CITY, SegType.DISTRICT, 0.0),
            (SegType.CITY, SegType.TOWN, 1.0),
            (SegType.CITY, SegType.ROAD, 2.0),
            (SegType.DISTRICT, SegType.TOWN, 0.0),
            (SegType.DISTRICT, SegType.ROAD, 1.0),
            (SegType.DISTRICT, SegType.VILLAGE, 1.0),
            (SegType.TOWN, SegType.VILLAGE, 0.0),
            (SegType.TOWN, SegType.COMMUNITY, 0.0),
            (SegType.TOWN, SegType.ROAD, 0.5),
            (SegType.TOWN, SegType.POI, 2.0),
            (SegType.VILLAGE, SegType.ROAD, 0.5),
            (SegType.VILLAGE, SegType.POI, 2.0),
            (SegType.COMMUNITY, SegType.ROAD, 0.5),
            (SegType.COMMUNITY, SegType.POI, 2.0),
            (SegType.ROAD, SegType.POI, 1.0),
            (SegType.ROAD, SegType.POI_SUB, 1.0),
            (SegType.ROAD, SegType.NUMERIC, 0.5),
            (SegType.ROAD, SegType.ORIENTATION, 0.2),
            (SegType.ROAD, SegType.LOCATION, 0.2),
            (SegType.POI, SegType.POI_SUB, 0.5),
            (SegType.POI, SegType.LOCATION, 0.3),
            (SegType.POI, SegType.ORIENTATION, 0.3),
            (SegType.ORIENTATION, SegType.ROAD, 0.0),
            (SegType.ORIENTATION, SegType.POI, 1.0),
            (SegType.ORIENTATION, SegType.LOCATION, 0.5),
            (SegType.LOCATION, SegType.ORIENTATION, 0.3),
            (SegType.NUMERIC, SegType.ROAD, 0.5),
            (SegType.NUMERIC, SegType.POI, 1.0),
            (SegType.NUMERIC, SegType.ORIENTATION, 0.3),
        ]
        for a, b, cost in valid:
            self.transition_cost[(a, b)] = cost

        same_type_ok = {SegType.ROAD, SegType.POI, SegType.POI_SUB, SegType.NUMERIC}
        for t in same_type_ok:
            self.transition_cost[(t, t)] = 1.0

    def recognize(self, text: str) -> AddressResult:
        text = text.strip()
        if not text:
            return AddressResult(original=text)

        matches = self._find_matches(text)
        matches_by_start = {}
        for s, e, stype, freq in matches:
            matches_by_start.setdefault(s, []).append((s, e, stype, freq))

        n = len(text)
        dp = [(float("inf"), -1, SegType.UNKNOWN, 0.0, "") for _ in range(n + 1)]
        dp[0] = (0.0, -1, SegType.UNKNOWN, 0.0, "")

        for i in range(n):
            if dp[i][0] >= float("inf") * 0.5:
                continue

            prev_type = dp[i][2]
            candidate_matches = matches_by_start.get(i, [])

            if candidate_matches:
                for start, end, seg_type, freq in candidate_matches:
                    word = text[start:end]
                    word_cost = self._word_cost(seg_type, freq, len(word))
                    trans_cost = self._transition_cost(prev_type, seg_type)
                    total_cost = dp[i][0] + word_cost + trans_cost

                    if total_cost < dp[end][0]:
                        dp[end] = (total_cost, i, seg_type, freq, word)

            single_char_cost = self._single_char_cost()
            trans_cost = self._transition_cost(prev_type, SegType.CHAR)
            total_cost = dp[i][0] + single_char_cost + trans_cost

            if total_cost < dp[i + 1][0]:
                dp[i + 1] = (total_cost, i, SegType.CHAR, 0.0, text[i])

        segments = self._backtrack(dp, text)

        segments = self._merge_orientation(segments)
        segments = self._merge_location(segments)
        segments = self._merge_same_type(segments)
        segments = self._assign_poi_types(segments)
        segments = self._cleanup_chars(segments, text)

        return AddressResult(original=text, segments=segments)

    def _find_matches(self, text: str) -> List[Tuple[int, int, SegType, int]]:
        matches = []
        n = len(text)
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

        admin_patterns = self._find_admin_patterns(text, n)
        matches.extend(admin_patterns)

        location_patterns = self._find_location_patterns(text, n)
        matches.extend(location_patterns)

        return matches

    def _find_admin_patterns(self, text: str, n: int) -> List[Tuple[int, int, SegType, int]]:
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

        return self._generate_pattern_matches(text, n, suffix_positions)

    def _find_location_patterns(self, text: str, n: int) -> List[Tuple[int, int, SegType, int]]:
        matches = []
        for sfx in LOCATION_SUFFIX_MAP:
            pos = text.find(sfx)
            while pos >= 0:
                end = pos + len(sfx)
                matches.append((pos, end, SegType.LOCATION, 0))
                pos = text.find(sfx, end)
        return matches

    def _generate_pattern_matches(self, text: str, n: int,
                                   positions: list) -> List[Tuple[int, int, SegType, int]]:
        TYPE_PRIORITY = {
            SegType.PROVINCE: 0, SegType.CITY: 1, SegType.DISTRICT: 2,
            SegType.TOWN: 3, SegType.VILLAGE: 4, SegType.COMMUNITY: 5,
            SegType.ROAD: 6, SegType.POI: 7, SegType.LOCATION: 8,
        }
        positions.sort(key=lambda x: (x[0], -len(x[2]), TYPE_PRIORITY.get(x[3], 9)))

        merged = []
        for end, spos, sfx, stype in positions:
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
            if len(word) > 1 and len(word) >= len(sfx):
                if word not in self.all_words:
                    matches.append((last_boundary, end, stype, 0))
            last_boundary = end

        return matches

    def _word_cost(self, seg_type: SegType, freq: int, length: int) -> float:
        if freq == 0:
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

        total = self.total_freq.get(seg_type, 1)
        if total == 0:
            total = 1
        idf = -math.log((freq + 1) / (total + 1))

        if length <= 1:
            length_penalty = 1.5
        elif length <= 2:
            length_penalty = 0.5
        elif length <= 8:
            length_penalty = 0.0
        else:
            length_penalty = (length - 8) * 0.3

        base_cost = max(0.5, idf + length_penalty + 1.0)
        return base_cost

    def _single_char_cost(self) -> float:
        return 3.0

    def _transition_cost(self, from_type: SegType, to_type: SegType) -> float:
        if from_type == SegType.UNKNOWN:
            start_penalties = {
                SegType.PROVINCE: 0.0,
                SegType.CITY: 1.0,
                SegType.DISTRICT: 2.0,
                SegType.TOWN: 2.0,
                SegType.VILLAGE: 3.0,
                SegType.COMMUNITY: 3.0,
                SegType.CHAR: 3.0,
            }
            return start_penalties.get(to_type, 5.0)
        return self.transition_cost.get((from_type, to_type), 5.0)

    def _backtrack(self, dp, text: str) -> List[AddressSegment]:
        n = len(text)
        segments = []
        pos = n
        while pos > 0:
            cost, prev, seg_type, freq, word = dp[pos]
            if pos == prev:
                break
            if seg_type != SegType.CHAR:
                segments.append(AddressSegment(
                    text=word,
                    seg_type=seg_type,
                    start=prev,
                    end=pos,
                    confidence=1.0 / (1.0 + cost),
                ))
            else:
                segments.append(AddressSegment(
                    text=text[prev:pos],
                    seg_type=SegType.UNKNOWN,
                    start=prev,
                    end=pos,
                    confidence=0.3,
                ))
            pos = prev

        segments.reverse()
        return segments

    def _merge_orientation(self, segments: List[AddressSegment]) -> List[AddressSegment]:
        if not segments:
            return segments

        result = []
        i = 0
        while i < len(segments):
            seg = segments[i]

            if seg.seg_type == SegType.ORIENTATION and i + 1 < len(segments):
                next_seg = segments[i + 1]
                if next_seg.seg_type in (SegType.ROAD, SegType.POI, SegType.TOWN,
                                           SegType.LOCATION, SegType.UNKNOWN):
                    merged = AddressSegment(
                        text=seg.text + next_seg.text,
                        seg_type=next_seg.seg_type if next_seg.seg_type != SegType.UNKNOWN else SegType.UNKNOWN,
                        start=seg.start,
                        end=next_seg.end,
                        confidence=(seg.confidence + next_seg.confidence) / 2,
                    )
                    result.append(merged)
                    i += 2
                    continue
            result.append(seg)
            i += 1

        return result

    def _merge_location(self, segments: List[AddressSegment]) -> List[AddressSegment]:
        if not segments:
            return segments
        result = []
        for seg in segments:
            if seg.seg_type == SegType.LOCATION and result and \
               result[-1].seg_type in (SegType.ROAD, SegType.POI, SegType.TOWN, SegType.UNKNOWN):
                result[-1].text += seg.text
                result[-1].end = seg.end
            else:
                result.append(seg)
        return result

    def _merge_same_type(self, segments: List[AddressSegment]) -> List[AddressSegment]:
        if not segments:
            return segments

        result = []
        for seg in segments:
            if result and seg.seg_type == result[-1].seg_type:
                if seg.seg_type in (SegType.POI, SegType.POI_SUB, SegType.LOCATION,
                                     SegType.CHAR, SegType.UNKNOWN):
                    result[-1].text += seg.text
                    result[-1].end = seg.end
                    continue
            result.append(seg)

        return result

    def _assign_poi_types(self, segments: List[AddressSegment]) -> List[AddressSegment]:
        for seg in segments:
            if seg.seg_type == SegType.POI:
                seg.poi_type = self._detect_poi_type(seg.text)
            elif seg.seg_type == SegType.POI_SUB:
                seg.poi_type = self._detect_poi_type(seg.text)
        return segments

    def _detect_poi_type(self, text: str) -> Optional[str]:
        for sfx, cat in sorted(POI_SUFFIX_MAP.items(), key=lambda x: -len(x[0])):
            if text.endswith(sfx):
                return cat
        from loc.importer import classify_suffix
        return classify_suffix(text)

    def _cleanup_chars(self, segments: List[AddressSegment], text: str) -> List[AddressSegment]:
        result = []
        for seg in segments:
            if seg.seg_type == SegType.CHAR:
                cleaned = seg.text.strip()
                cleaned = "".join(ch for ch in cleaned if ch not in STOP_CHARS)
                if not cleaned:
                    continue
                seg = AddressSegment(
                    text=cleaned,
                    seg_type=SegType.UNKNOWN,
                    start=seg.start,
                    end=seg.end,
                    confidence=0.2,
                )
            result.append(seg)

        merged = []
        for seg in result:
            if seg.seg_type == SegType.UNKNOWN and merged and merged[-1].seg_type == SegType.UNKNOWN:
                merged[-1].text += seg.text
                merged[-1].end = seg.end
            else:
                merged.append(seg)

        return merged
