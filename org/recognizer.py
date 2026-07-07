"""机构名识别器 V5 — Viterbi DP (复用地址DP框架)"""

import os, csv, math, pickle, logging
logger = logging.getLogger(__name__)
from typing import Dict, List, Tuple
from core.types import SegType, AddressSegment, AddressResult, LEVEL_ORDER
from loc.importer import classify_suffix


class OrgDPRecognizer:
    def __init__(self, data_dir: str, version: str = "v1.1.1",
                 disable_short_d4_penalty: bool = False, allow_adjacent_d4: bool = False,
                 poi_seed_path: str = None, dict_name: str = None):
        self.trie = {}
        self.total_freq = {}
        self._d4_set = set()
        self._brand_model = None
        self._version = version
        self._disable_short_d4_penalty = disable_short_d4_penalty
        self._allow_adjacent_d4 = allow_adjacent_d4
        self._poi_seed_path = poi_seed_path
        self._dict_name = dict_name
        self.d3_set = set()
        self._build_trie(data_dir)
        self._build_transition_costs()

    @property
    def d4_suffixes(self):
        return sorted(self._d4_set, key=lambda x: -len(x))

    @property
    def d3_words(self):
        return sorted(self.d3_set, key=lambda x: -len(x))

    def brand_score(self, text: str) -> float:
        if self._brand_model is None:
            self._load_brand_model()
        if self._brand_model is None:
            return 0.5
        return self._brand_model.brand_score(text)

    def _load_brand_model(self):
        from brand.model import BrandModel
        base = os.path.dirname(os.path.dirname(__file__))
        dict_dir = os.path.join(base, "dicts")
        for ver in (self._version, "v1.1.2", "v1.1.1", ""):
            bm = BrandModel(dict_dir, version=ver) if ver else BrandModel(dict_dir)
            if bm.load():
                self._brand_model = bm
                logger.info(f"  Loaded brand model {ver}")
                return
        logger.info(f"  No brand model found")

    # ── Trie: areas/ (d1) + d333 (d3) + d444 (d4) ──

    def _build_trie(self, data_dir: str):
        trie = {}
        freq = {}

        # Load pruned d1/d3/d4 from cache
        if self._dict_name:
            cache_path = os.path.join(os.path.dirname(data_dir), "dicts", self._dict_name)
        else:
            cache_path = os.path.join(os.path.dirname(data_dir), "dicts",
                                      f"org_{self._version}.pkl")
            if not os.path.exists(cache_path):
                for fallback in ("v1.1.1", ""):
                    fb = os.path.join(os.path.dirname(data_dir), "dicts",
                                      f"org_{fallback}.pkl" if fallback else "org.pkl")
                    if os.path.exists(fb):
                        cache_path = fb
                        break
        d1_freqs = {}
        d3_freqs = {}
        d4_freqs = {}
        if os.path.exists(cache_path):
            with open(cache_path, "rb") as f:
                try:
                    cached = pickle.load(f)
                except (pickle.UnpicklingError, EOFError, AttributeError) as e:
                    raise ValueError(f"Corrupted dict file: {cache_path} ({e})") from e
            d1_freqs = cached.get("d1_freqs", {})
            d3_freqs = cached.get("d3_freqs", {})
            d4_freqs = cached.get("d4_freqs", {})
        logger.info(f"  Loaded pruned: d1={len(d1_freqs)}, d3={len(d3_freqs)}, d4={len(d4_freqs)}")

        # d1: from pruned freqs (type inferred by suffix, bare name as fallback)
        from core.types import ADMIN_SUFFIX_MAP
        bare_name_type = self._build_bare_name_table(data_dir)
        for bare_name, btype in bare_name_type.items():
            if bare_name not in d1_freqs:
                d1_freqs[bare_name] = 5000
        self._inject_d111_missing(data_dir, d1_freqs, cache_path)

        for w, f in d1_freqs.items():
            st = SegType.ROAD
            for t, suffixes in sorted(ADMIN_SUFFIX_MAP.items(), key=lambda x: -len(x[0].value)):
                for sfx in sorted(suffixes, key=lambda x: -len(x)):
                    if w.endswith(sfx) and len(w) > len(sfx):
                        st = t; break
                if st != SegType.ROAD: break
            if st == SegType.ROAD and w in bare_name_type:
                st = bare_name_type[w]
            node = trie
            for ch in w:
                node = node.setdefault(ch, {})
            cur = node.get("#")
            # Type collision: higher admin priority wins (PROVINCE > CITY > DISTRICT > ... > POI)
            if cur is None:
                node["#"] = (st, f)
            else:
                cur_type, cur_freq = cur
                new_prio = LEVEL_ORDER.get(st, 99)
                old_prio = LEVEL_ORDER.get(cur_type, 99)
                if new_prio < old_prio or (new_prio == old_prio and f > cur_freq):
                    node["#"] = (st, f)
            freq[st] = freq.get(st, 0) + 1

        # d3: pruned industry words (use LOCATION type)
        self.d3_set = set()
        d3_count = 0
        for w, f in d3_freqs.items():
            self.d3_set.add(w)
            node = trie
            for ch in w:
                node = node.setdefault(ch, {})
            cur = node.get("#")
            if cur is None:
                node["#"] = (SegType.INDUSTRY, f)
            else:
                cur_type, cur_freq = cur
                new_prio = LEVEL_ORDER.get(SegType.INDUSTRY, 99)
                old_prio = LEVEL_ORDER.get(cur_type, 99)
                if new_prio < old_prio or (new_prio == old_prio and f > cur_freq):
                    node["#"] = (SegType.INDUSTRY, f)
            d3_count += 1
        freq[SegType.INDUSTRY] = max(1, d3_count)

        # d4: pruned org suffixes
        d4_count = 0
        for sfx, f in d4_freqs.items():
            node = trie
            for ch in sfx:
                node = node.setdefault(ch, {})
            cur = node.get("#")
            if cur is None:
                node["#"] = (SegType.POI, f)
            else:
                cur_type, cur_freq = cur
                new_prio = LEVEL_ORDER.get(SegType.POI, 99)
                old_prio = LEVEL_ORDER.get(cur_type, 99)
                if new_prio < old_prio or (new_prio == old_prio and f > cur_freq):
                    node["#"] = (SegType.POI, f)
            self._d4_set.add(sfx)
            d4_count += 1

        if self._poi_seed_path:
            d4_count += self._inject_poi_seed_d4(self._poi_seed_path, d4_freqs, trie)
        freq[SegType.POI] = max(1, d4_count)

        self.trie = trie
        self.total_freq = freq

        counts = {SegType.PROVINCE: "PROVINCE", SegType.CITY: "CITY",
                  SegType.DISTRICT: "DISTRICT", SegType.TOWN: "TOWN",
                  SegType.VILLAGE: "VILLAGE", SegType.COMMUNITY: "COMMUNITY",
                  SegType.ROAD: "ROAD", SegType.INDUSTRY: "d3", SegType.POI: "d4"}
        for st, label in counts.items():
            logger.info(f"  {label:12s}: {freq.get(st, 0):>8,}")

    def _build_bare_name_table(self, data_dir: str) -> dict:
        """Build {bare_name: SegType} from areas/ for province/city/district/town bare names."""
        table = {}
        areas_dir = os.path.join(os.path.dirname(data_dir), "data", "areas")
        if not os.path.isdir(areas_dir):
            areas_dir = os.path.join(data_dir, "areas")

        suffix_to_type = {
            "维吾尔自治区": SegType.PROVINCE, "回族自治区": SegType.PROVINCE,
            "壮族自治区": SegType.PROVINCE, "特别行政区": SegType.PROVINCE,
            "省": SegType.PROVINCE, "自治区": SegType.PROVINCE,
            "市": SegType.CITY, "自治州": SegType.CITY, "地区": SegType.CITY, "盟": SegType.CITY,
            "自治县": SegType.DISTRICT, "自治旗": SegType.DISTRICT,
            "区": SegType.DISTRICT, "县": SegType.DISTRICT, "旗": SegType.DISTRICT,
            "办事处": SegType.TOWN, "民族乡": SegType.TOWN, "苏木": SegType.TOWN,
            "镇": SegType.TOWN, "乡": SegType.TOWN, "街道": SegType.TOWN,
        }

        for fname, default_type in [("provinces.csv", SegType.PROVINCE),
                                     ("cities.csv", SegType.CITY),
                                     ("areas.csv", SegType.DISTRICT),
                                     ("streets.csv", SegType.TOWN)]:
            path = os.path.join(areas_dir, fname)
            if not os.path.exists(path):
                continue
            try:
                with open(path, encoding="utf-8-sig") as f:
                    for row in csv.DictReader(f):
                        name = row.get("name", "").strip()
                        if not name or len(name) < 3:
                            continue
                        for sfx, stype in sorted(suffix_to_type.items(), key=lambda x: -len(x[0])):
                            if name.endswith(sfx) and len(name) > len(sfx):
                                bare = name[:-len(sfx)]
                                if len(bare) >= 2:
                                    existing = table.get(bare)
                                    if existing is None:
                                        table[bare] = stype
                                    else:
                                        # keep higher-priority type (lower LEVEL_ORDER value)
                                        if LEVEL_ORDER.get(stype, 99) < LEVEL_ORDER.get(existing, 99):
                                            table[bare] = stype
                                break
            except (FileNotFoundError, UnicodeDecodeError, csv.Error) as e:
                import warnings
                warnings.warn(f"Failed to load bare name table from {path}: {e}")
        return table

    def _inject_d111_missing(self, data_dir: str, d1_freqs: dict, cache_path: str):
        """Scan addr_segments_sql.csv for admin names missing from d1_freqs and inject them.
        Only runs when loading from an older version (fallback), not when current version exists."""
        if self._dict_name:
            return  # Custom dict (e.g. POI), don't inject d111
        if self._version in cache_path:
            return  # Current version dict exists, skip injection
        d111_path = os.path.join(os.path.dirname(data_dir), "data", "addr_segments_sql.csv")
        if not os.path.exists(d111_path):
            return

        SUFFIX_TYPE = {
            "自治县": SegType.DISTRICT, "自治旗": SegType.DISTRICT,
            "区": SegType.DISTRICT, "县": SegType.DISTRICT, "旗": SegType.DISTRICT,
            "镇": SegType.TOWN, "乡": SegType.TOWN,
        }
        GENERIC = {"新区", "东区", "南区", "西区", "北区", "中区",
                   "城区", "片区", "园区", "矿区", "林区", "特区",
                   "乡村", "城乡", "城镇", "山镇", "水乡", "山乡", "渔乡"}

        injected = 0
        with open(d111_path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                word = row["d1"].strip()
                if not word or len(word) < 2:
                    continue
                if word in d1_freqs or word in GENERIC:
                    continue
                try:
                    tf = max(1, int(row.get("tf1", 0) or 0))
                except ValueError:
                    tf = 1
                if tf < 20:
                    continue

                for sfx, stype in sorted(SUFFIX_TYPE.items(), key=lambda x: -len(x[0])):
                    if word.endswith(sfx) and len(word) > len(sfx):
                        d1_freqs[word] = max(d1_freqs.get(word, 0), tf)
                        injected += 1
                        break

        logger.info(f"  Injected {injected} d111 admin names into d1")

    def _inject_poi_seed_d4(self, seed_path: str, d4_freqs: dict, trie: dict) -> int:
        """Inject POI suffix seed into d4_freqs to bootstrap DP recognition."""
        injected = 0
        with open(seed_path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                sfx = row["sfx"].strip()
                if not sfx or len(sfx) < 2:
                    continue
                if sfx in d4_freqs:
                    continue
                try:
                    tf = int(row.get("tf1", 0) or 0)
                except ValueError:
                    tf = 1
                if tf < 100:
                    continue
                d4_freqs[sfx] = tf
                node = trie
                for ch in sfx:
                    node = node.setdefault(ch, {})
                cur = node.get("#")
                if cur is None:
                    node["#"] = (SegType.POI, tf)
                else:
                    cur_type, cur_freq = cur
                    new_prio = LEVEL_ORDER.get(SegType.POI, 99)
                    old_prio = LEVEL_ORDER.get(cur_type, 99)
                    if new_prio < old_prio or (new_prio == old_prio and tf > cur_freq):
                        node["#"] = (SegType.POI, tf)
                self._d4_set.add(sfx)
                injected += 1
        logger.info(f"  Injected {injected} POI seed d4 entries")
        return injected

    # ── Transition costs ──

    # ── Transition cost table: cost=0.0 free, 0.2-0.5 cheap, 1.0-2.0 normal, 5.0 disallowed.
    # Values determined empirically via eval.py scoring. Lower cost = transition preferred.
    def _build_transition_costs(self):
        self.trans = {}

        # Default: 5.0 for all
        all_t = [SegType.PROVINCE, SegType.CITY, SegType.DISTRICT, SegType.TOWN,
                 SegType.VILLAGE, SegType.COMMUNITY, SegType.ROAD, SegType.UNKNOWN, SegType.POI,
                 SegType.INDUSTRY]
        for a in all_t:
            for b in all_t:
                self.trans[(a, b)] = 5.0

        # Valid transitions (d1=addr types, d2/d3=UNKNOWN, d4=POI)
        addr_types = [SegType.PROVINCE, SegType.CITY, SegType.DISTRICT,
                      SegType.TOWN, SegType.VILLAGE, SegType.COMMUNITY, SegType.ROAD]

        # START → addr: 0.0
        for t in addr_types:
            self.trans[(SegType.UNKNOWN, t)] = 0.0

        # START → POI(d4): 2.0 (e.g. "XXX有限公司" without address)
        self.trans[(SegType.UNKNOWN, SegType.POI)] = 2.0

        # addr → addr: 0.0 (连续行政区划)
        for a in addr_types:
            for b in addr_types:
                self.trans[(a, b)] = 0.0

        # addr → UNKNOWN(d2/d3): 0.3
        for a in addr_types:
            self.trans[(a, SegType.UNKNOWN)] = 0.3

        # addr → POI(d4): 1.0
        for a in addr_types:
            self.trans[(a, SegType.POI)] = 1.0

        # UNKNOWN → UNKNOWN: 1.5 (品牌+行业, 允许连续但偏贵)
        self.trans[(SegType.UNKNOWN, SegType.UNKNOWN)] = 1.5

        # UNKNOWN(d2)→POI: 0.2
        self.trans[(SegType.UNKNOWN, SegType.POI)] = 0.2
        # LOCATION(d3)→POI: 0.0
        self.trans[(SegType.INDUSTRY, SegType.POI)] = 0.0
        # UNKNOWN(d2)→LOCATION(d3): 0.3
        self.trans[(SegType.UNKNOWN, SegType.INDUSTRY)] = 0.3
        # LOCATION→LOCATION: 5.0 (don't merge adjacent d3)
        self.trans[(SegType.INDUSTRY, SegType.INDUSTRY)] = 5.0
        # LOCATION→UNKNOWN: 1.0
        self.trans[(SegType.INDUSTRY, SegType.UNKNOWN)] = 1.0
        # addr→LOCATION(d3): 0.5
        for a in addr_types:
            self.trans[(a, SegType.INDUSTRY)] = 0.5

        # POI → anything: 5.0 (d4是终点, 不应该再接东西)
        # For POI mode: allow adjacent d4
        if self._allow_adjacent_d4:
            self.trans[(SegType.POI, SegType.POI)] = 1.5
            self.trans[(SegType.POI, SegType.UNKNOWN)] = 2.0

    def _transition_cost(self, from_type: SegType, to_type: SegType) -> float:
        return self.trans.get((from_type, to_type), 5.0)

    # ── Word cost ──

    def _word_cost(self, seg_type: SegType, freq: int, length: int) -> float:
        if freq == 0:
            if length <= 2: return 2.0
            elif length <= 4: return 2.5
            elif length <= 8: return 3.0
            else: return 4.0

        total = self.total_freq.get(seg_type, 1)
        if total <= 0: total = 1
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

    def _single_char_cost(self) -> float:
        return 2.0

    # ── Trie matches ──

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
        return matches

    # ── Main ──

    def recognize(self, text: str) -> AddressResult:
        raw_text = text
        text = text.strip()
        if not text:
            return AddressResult(original=raw_text)

        matches = self._find_matches(text)
        by_start = {}
        for s, e, stype, freq in matches:
            by_start.setdefault(s, []).append((s, e, stype, freq))

        n = len(text)
        START = SegType.UNKNOWN
        dp = [(float("inf"), -1, START, 0.0, "") for _ in range(n + 1)]
        dp[0] = (0.0, -1, START, 0.0, "")

        for i in range(n):
            if dp[i][0] >= float("inf") * 0.5:
                continue
            prev_type = dp[i][2]

            for start, end, seg_type, freq in by_start.get(i, []):
                wc = self._word_cost(seg_type, freq, end - start)
                # Short-d4 penalty: 2-3 char POI suffixes with freq<50K and not near end of text
                # get a heavy cost boost (7.0) to prevent short, common suffixes from
                # hijacking the DP path. Disabled for POI mode (disable_short_d4_penalty=True).
                if not self._disable_short_d4_penalty and seg_type == SegType.POI and 2 <= (end - start) <= 3 and freq < 50000 and end < n * 0.8:
                    wc = max(wc, 7.0)
                tc = self._transition_cost(prev_type, seg_type)
                total = dp[i][0] + wc + tc
                if total < dp[end][0]:
                    dp[end] = (total, i, seg_type, freq, text[start:end])

            scc = self._single_char_cost()
            tc = self._transition_cost(prev_type, SegType.UNKNOWN)
            total = dp[i][0] + scc + tc
            if total < dp[i + 1][0]:
                dp[i + 1] = (total, i, SegType.UNKNOWN, 0.0, text[i])

        # Backtrack
        segments = []
        pos = n
        while pos > 0:
            cost, prev, stype, freq, word = dp[pos]
            if pos == prev:
                break
            segment_cost = max(cost - dp[prev][0], 0.01)
            cf = 1.0 / (1.0 + segment_cost)
            segments.append(AddressSegment(
                text=word, seg_type=stype, start=prev, end=pos,
                confidence=cf,
            ))
            pos = prev
        segments.reverse()

        # Assign POI types to d4 segments
        addr_types = {SegType.PROVINCE, SegType.CITY, SegType.DISTRICT,
                      SegType.TOWN, SegType.VILLAGE, SegType.COMMUNITY, SegType.ROAD}
        for s in segments:
            if s.seg_type == SegType.POI:
                s.poi_type = classify_suffix(s.text)

        # Merge consecutive UNKNOWN segments (d2+d3 can be adjacent)
        merged = []
        for s in segments:
            if merged and s.seg_type == SegType.UNKNOWN and merged[-1].seg_type == SegType.UNKNOWN:
                merged[-1].text += s.text
                merged[-1].end = s.end
            else:
                merged.append(s)

        # Merge trailing single-char UNKNOWN into predecessor (before relabel)
        TRAILING_SINGLE = {"店", "厂", "站", "路", "村", "屯", "镇", "乡", "街",
                           "馆", "铺", "坊", "档", "摊", "所", "局", "处", "阁",
                           "苑", "城", "园", "庭", "屋", "舍", "汇", "行", "场"}
        if len(merged) >= 2:
            last = merged[-1]
            prev = merged[-2]
            if last.seg_type == SegType.UNKNOWN and len(last.text) == 1 \
               and prev.seg_type in (SegType.INDUSTRY, SegType.POI, SegType.ROAD):
                if last.text in TRAILING_SINGLE or prev.seg_type == SegType.POI:
                    prev.text += last.text
                    prev.end = last.end
                    prev.seg_type = SegType.POI
                    prev.poi_type = classify_suffix(prev.text)
                    merged.pop()

        # Tag remaining UNKNOWN segments as BRAND
        for s in merged:
            if s.seg_type == SegType.UNKNOWN:
                s.seg_type = SegType.BRAND

        return AddressResult(original=raw_text, segments=merged)
