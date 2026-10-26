import csv
import logging
import os
import threading
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
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return result
        idx = {name: i for i, name in enumerate(header)}
        if key_col not in idx:
            raise ValueError(f"{path}: missing column {key_col!r}")
        key_i = idx[key_col]
        com_i, org_i, loc_i = idx.get("com"), idx.get("org"), idx.get("loc")

        def cell(row, i):
            if i is None or i >= len(row):
                return 0
            value = row[i].strip()
            return int(value) if value else 0

        for row in reader:
            if key_i >= len(row):
                continue
            word = row[key_i].strip()
            if not word:
                continue
            if len(word) == 1 and word not in SAFE_SINGLE:
                continue
            try:
                com = cell(row, com_i)
                org = cell(row, org_i)
                loc = cell(row, loc_i)
            except ValueError:
                continue
            if org == 0 and loc == 0 and com == 0:
                continue
            result[word] = AffinityEntry(word, org, loc, com)
    return result


class CsvIndex:
    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self):
        self._suffix = None
        self._trade = None
        self._addr = None
        self._trade_max_len = 0
        self._trade_order = {}
        self._lock = threading.Lock()

    @classmethod
    def instance(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def suffix(self):
        if self._suffix is None:
            with self._lock:
                if self._suffix is None:
                    self._suffix = _load_affinity_csv(
                        os.path.join(DATA_DIR, "suffix_segments_sql.csv"), "d4")
        return self._suffix

    @property
    def trade(self):
        if self._trade is None:
            with self._lock:
                if self._trade is None:
                    self._trade = _load_affinity_csv(
                        os.path.join(DATA_DIR, "trade_segments_sql.csv"), "d3")
                    self._trade_max_len = max((len(w) for w in self._trade), default=0)
                    self._trade_order = {w: i for i, w in enumerate(self._trade)}
        return self._trade

    @property
    def addr(self):
        if self._addr is None:
            with self._lock:
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
        """返回 text 中出现的最长 trade 词条; 子串枚举替代全表扫描。

        旧实现每次遍历 4 万条 trade 词, 含行业段文本单条 ~1.1ms;
        现在按长度降序枚举 text 子串, 复杂度 O(L^2), L 为行业段文本长度。
        """
        if not text or not self.trade:
            return None
        max_len = min(len(text), self._trade_max_len)
        for length in range(max_len, 0, -1):
            best = None
            best_order = None
            for start in range(0, len(text) - length + 1):
                w = text[start:start + length]
                entry = self.trade.get(w)
                if entry is not None:
                    order = self._trade_order[w]
                    if best is None or order < best_order:
                        best, best_order = entry, order
            if best is not None:
                return best
        return None

    def lookup_addr(self, text):
        if not text or not self.addr:
            return None
        for end in range(len(text), 0, -1):
            w = text[:end]
            if w in self.addr:
                return self.addr[w]
        return None
