"""词典构建器 V5 — loc3.6kw idf词频 + areas五级区划 + d444 POI"""

import os, time, pickle, csv
from collections import Counter, defaultdict
from typing import Dict, List, Set, Tuple, Optional
from core.types import SegType, ADMIN_SUFFIX_MAP, LOCATION_SUFFIX_SET, POI_SUFFIX_MAP


class DictBuilder:
    def __init__(self, cache_dir: str, version: str = "v1.1.2"):
        self.cache_dir = cache_dir
        self.version = version
        self.dict_data: Dict[SegType, Dict[str, int]] = defaultdict(dict)
        os.makedirs(cache_dir, exist_ok=True)

    # ── Phase 1: loc3.6kw idf-based counters (replaces self-mined + d111) ──

    def build_from_loc36kw(self, data_dir: str):
        split_dir = os.path.join(data_dir, "split", "loc")
        chunk_files = sorted([
            os.path.join(split_dir, f) for f in os.listdir(split_dir)
            if f.startswith("chunk_") and f.endswith(".csv")
        ])
        cache_path = os.path.join(self.cache_dir, f"loc36kw_counters_{self.version}.pkl")

        if os.path.exists(cache_path):
            t0 = time.time()
            with open(cache_path, "rb") as f:
                counters = pickle.load(f)
            print(f"  Loaded loc3.6kw counters from cache ({time.time()-t0:.1f}s)")
        else:
            counters = self._scan_loc36kw_chunks(chunk_files)
            with open(cache_path, "wb") as f:
                pickle.dump(counters, f, pickle.HIGHEST_PROTOCOL)
            print(f"  Cached loc3.6kw counters ({os.path.getsize(cache_path)/1024/1024:.0f}MB)")

        thresholds = {
            SegType.DISTRICT: 5, SegType.TOWN: 5, SegType.VILLAGE: 5,
            SegType.COMMUNITY: 5, SegType.ROAD: 3, SegType.PROVINCE: 3,
            SegType.CITY: 5,
        }
        caps = {SegType.VILLAGE: 150000, SegType.COMMUNITY: 150000,
                SegType.ROAD: 150000}

        for st, counter in counters.items():
            thresh = thresholds.get(st, 3)
            cap = caps.get(st, 999999)
            kept = 0
            for word, idf_sum in counter.most_common(cap):
                if idf_sum < thresh:
                    continue
                cur = self.dict_data[st].get(word, 0)
                if idf_sum > cur:
                    self.dict_data[st][word] = idf_sum
                    kept += 1
            print(f"  {st.value:15s}: {kept:>8,} (idf>={thresh})")

    def _scan_loc36kw_chunks(self, files: list):
        from loc.importer import _split_admin
        total_size_mb = sum(os.path.getsize(f) for f in files) / 1024 / 1024
        print(f"  Scanning loc3.6kw from {len(files)} chunks ({total_size_mb:.0f}MB)...")
        t0 = time.time()
        counters = defaultdict(Counter)
        i = 0
        for fp in files:
            with open(fp, encoding="utf-8") as f:
                next(f)  # skip header
                for line in f:
                    parts = line.strip().rsplit(",", 1)
                    if len(parts) != 2:
                        continue
                    text, idf_s = parts[0].strip(), parts[1].strip()
                    if not text or len(text) < 2:
                        continue
                    try:
                        idf = max(1, int(float(idf_s)))
                    except ValueError:
                        idf = 1

                    comps = _split_admin(text)
                    for comp, st in comps:
                        counters[st][comp] += idf

                    i += 1
                    if i % 5000000 == 0:
                        elapsed = time.time() - t0
                        print(f"    {i//10000:>4}w rows ({elapsed:.0f}s)")

        print(f"    {i:,} rows in {time.time()-t0:.0f}s")
        return counters

    # ── Phase 2: d444 POI suffixes ──

    def build_from_d444(self, data_dir: str):
        path = os.path.join(data_dir, "suffix_segments_sql.csv")
        c = 0
        with open(path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                sfx = row["d4"].strip()
                if not sfx or len(sfx) < 2:
                    continue
                try:
                    tf = int(row["tf1"])
                except (ValueError, KeyError):
                    tf = 1
                if tf < 10:
                    continue
                self.dict_data[SegType.POI][sfx] = max(
                    self.dict_data[SegType.POI].get(sfx, 0), tf
                )
                c += 1
        print(f"  POI from d444: {c:,} entries")

    # ── Phase 3: Official 5-level admin areas ──

    def build_from_areas(self, data_dir: str):
        from loc.importer import import_areas
        areas = import_areas(data_dir)
        for st, entries in areas.items():
            for w, f in entries.items():
                self.dict_data[st][w] = max(self.dict_data[st].get(w, 0), f)
        counts = {k.value: len(v) for k, v in areas.items()}
        print(f"  Areas: {counts}")

    # ── Post-processing ──

    def cleanup(self):
        self._cleanup_road_entries()
        self._cleanup_poi_entries()
        self._cleanup_compound_entries()

    def _cleanup_road_entries(self):
        d = self.dict_data.get(SegType.ROAD, {})
        comp = set()
        for s in ADMIN_SUFFIX_MAP.values():
            comp.update(x for x in s if len(x) >= 2)
        comp = comp - {"段", "线"}
        rm = [w for w in d if any(s != w[-len(s):] and s in w for s in comp)]
        for w in rm:
            del d[w]
        if rm:
            print(f"  Cleaned {len(rm):,} road")

    def _cleanup_poi_entries(self):
        d = self.dict_data.get(SegType.POI, {})
        comp = set()
        for s in ADMIN_SUFFIX_MAP.values():
            comp.update(x for x in s if len(x) >= 2)
        rm = [w for w in d if any(s != w and s in w for s in comp)]
        for w in rm:
            del d[w]
        if rm:
            print(f"  Cleaned {len(rm):,} poi")

    def _cleanup_compound_entries(self):
        all_multi = set()
        for v in ADMIN_SUFFIX_MAP.values():
            all_multi.update(x for x in v if len(x) >= 2)
        for st in [SegType.DISTRICT, SegType.TOWN, SegType.VILLAGE]:
            d = self.dict_data.get(st, {})
            own = {x for x in ADMIN_SUFFIX_MAP.get(st, set()) if len(x) >= 2}
            other = all_multi - own
            rm = [w for w in d if any(s in w for s in other)]
            for w in rm:
                del d[w]
            if rm:
                print(f"  Cleaned {len(rm):,} compound {st.value}")

        d = self.dict_data.get(SegType.COMMUNITY, {})
        own = {x for x in ADMIN_SUFFIX_MAP.get(SegType.COMMUNITY, set()) if len(x) >= 2}
        other = all_multi - own
        rm = [w for w in d if any(s in w for s in other)]
        for w in rm:
            del d[w]
        if rm:
            print(f"  Cleaned {len(rm):,} compound COMMUNITY")

    def build_orientation_dict(self):
        for o in {"东","南","西","北","中","东北","西北","东南","西南",
                  "前","后","左","右","上","下","内","外"}:
            self.dict_data[SegType.ORIENTATION][o] = 100

    def build_location_dict(self):
        for loc in LOCATION_SUFFIX_SET:
            self.dict_data[SegType.LOCATION][loc] = 80

    # ── IO ──

    def save(self):
        path = os.path.join(self.cache_dir, f"{self.version}.pkl")
        with open(path, "wb") as f:
            pickle.dump(dict(self.dict_data), f, pickle.HIGHEST_PROTOCOL)
        print(f"  Saved: {path} ({os.path.getsize(path)/1024/1024:.0f}MB)")

    @classmethod
    def load(cls, cache_dir: str, version: str = "loc_v1.1.2"):
        path = os.path.join(cache_dir, f"{version}.pkl")
        if not os.path.exists(path):
            raise FileNotFoundError(f"No dict file: {path}")
        with open(path, "rb") as f:
            try:
                d = pickle.load(f)
            except (pickle.UnpicklingError, EOFError, AttributeError) as e:
                raise ValueError(f"Corrupted dict file: {path} ({e})") from e
        b = cls(cache_dir, version)
        b.dict_data = d
        return b
