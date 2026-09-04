import csv
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

SAFE_SINGLE = {"厂", "店", "站", "园", "局", "院"}


class AffinityEntry:
    __slots__ = ("word", "org", "loc", "com", "org_ratio", "loc_ratio")

    def __init__(self, word, org, loc, com):
        self.word = word
        self.org = org
        self.loc = loc
        self.com = com
        total = org + loc + com
        self.org_ratio = org / total if total > 0 else 0.0
        self.loc_ratio = loc / total if total > 0 else 0.0


def _load_affinity_csv(path, key_col):
    result = {}
    if not os.path.exists(path):
        logger.warning("亲和度 CSV 缺失, 亲和度特征置空 (静默降级, 见 HANDOVER §3.5): %s", path)
        return result
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            word = row[key_col].strip()
            if not word or len(word) < 1:
                continue
            if len(word) == 1 and word not in SAFE_SINGLE:
                continue
            try:
                com = int(row.get("com", 0) or 0)
                org = int(row.get("org", 0) or 0)
                loc = int(row.get("loc", 0) or 0)
            except (ValueError, KeyError):
                continue
            if org == 0 and loc == 0 and com == 0:
                continue
            result[word] = AffinityEntry(word, org, loc, com)
    return result


class CsvIndex:
    _instance = None

    def __init__(self):
        self._suffix = None
        self._trade = None
        self._addr = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def suffix(self):
        if self._suffix is None:
            self._suffix = _load_affinity_csv(
                os.path.join(DATA_DIR, "suffix_segments_sql.csv"), "d4")
        return self._suffix

    @property
    def trade(self):
        if self._trade is None:
            self._trade = _load_affinity_csv(
                os.path.join(DATA_DIR, "trade_segments_sql.csv"), "d3")
        return self._trade

    @property
    def addr(self):
        if self._addr is None:
            a = _load_affinity_csv(
                os.path.join(DATA_DIR, "addr_segments_sql.csv"), "d1")
            self._addr = {w: e for w, e in a.items()
                          if e.org >= 2 * max(e.loc, e.com)
                          or e.loc >= 2 * max(e.org, e.com)}
        return self._addr

    def lookup_suffix(self, text):
        if not text or not self.suffix:
            return None
        for end in range(len(text), 0, -1):
            for start in range(0, end):
                w = text[start:end]
                if w in self.suffix:
                    return self.suffix[w]
        return None

    def lookup_trade(self, text):
        if not text or not self.trade:
            return None
        best = None
        for w, e in self.trade.items():
            if w in text and (best is None or len(w) > len(best.word)):
                best = e
        return best

    def lookup_addr(self, text):
        if not text or not self.addr:
            return None
        for end in range(len(text), 0, -1):
            w = text[:end]
            if w in self.addr:
                return self.addr[w]
        return None
