"""品牌词 bigram 概率模型 — 从 d2_freqs CSV 训练"""

import os, csv, pickle, math, time
import logging
logger = logging.getLogger(__name__)
from collections import Counter


class BrandModel:
    def __init__(self, cache_dir: str, version: str = "v1.1.1"):
        self.cache_dir = cache_dir
        self.version = version
        self.bigram_counts = Counter()
        self.unigram_counts = Counter()
        self.total_bigrams = 0
        self.smoothing = 1

    @property
    def _path(self):
        return os.path.join(self.cache_dir, f"brand_{self.version}.pkl")

    def train_from_d2_csv(self, csv_path: str, min_freq: int = 2,
                          min_bigram_count: int = 5, max_lines: int = 0):
        """Train from org_d2_freqs CSV (columns: d2_text, freq) exported by org_aggregate."""
        t0 = time.time()
        size_mb = os.path.getsize(csv_path) / 1024 / 1024
        logger.info(f"  Training brand model from d2 CSV ({size_mb:.0f}MB,"
              f" d2_freq>={min_freq}, bigram_count>={min_bigram_count})...")

        total_in = 0
        total_kept = 0

        with open(csv_path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                text = row["d2_text"].strip()
                if not text or len(text) < 2:
                    continue

                try:
                    freq = int(row["freq"])
                except (ValueError, KeyError):
                    freq = 1

                total_in += 1
                if freq < min_freq:
                    continue
                total_kept += 1

                weight = freq

                for j in range(len(text)):
                    self.unigram_counts[text[j]] += weight

                for j in range(len(text) - 1):
                    pair = text[j] + text[j + 1]
                    self.bigram_counts[pair] += weight

                if max_lines and total_kept >= max_lines:
                    break

                if (i + 1) % 3000000 == 0:
                    elapsed = time.time() - t0
                    row_rate = (i + 1) / elapsed if elapsed > 0 else 0
                    logger.info(f"    {i//10000:>4}w rows, kept={total_kept:,}, "
                          f"{len(self.bigram_counts):,} bigrams, {row_rate:,.0f} rows/s")

        self.total_bigrams = sum(self.bigram_counts.values())
        elapsed = time.time() - t0
        logger.info(f"    Input: {total_in:,}, Kept (freq>={min_freq}): {total_kept:,}")
        logger.info(f"    {len(self.bigram_counts):,} bigrams (raw), "
              f"{len(self.unigram_counts):,} unigrams ({elapsed:.0f}s)")

        if min_bigram_count > 1:
            before = len(self.bigram_counts)
            self.bigram_counts = Counter({
                k: v for k, v in self.bigram_counts.items() if v >= min_bigram_count
            })
            self.total_bigrams = sum(self.bigram_counts.values())
            logger.info(f"    Bigram filter count>={min_bigram_count}: "
                  f"{before:,} → {len(self.bigram_counts):,} "
                  f"(-{before-len(self.bigram_counts):,}, "
                  f"{-100*(before-len(self.bigram_counts))/max(1,before):.0f}%)")

    def bigram_prob(self, ch1: str, ch2: str) -> float:
        """P(ch2 | ch1) with smoothing."""
        pair = ch1 + ch2
        count_pair = self.bigram_counts.get(pair, 0)
        count_ch1 = self.unigram_counts.get(ch1, 0)
        if count_ch1 == 0:
            return 1.0 / (len(self.unigram_counts) + self.smoothing)
        return (count_pair + self.smoothing) / (count_ch1 + self.smoothing * len(self.unigram_counts))

    def _avg_log_prob(self, text: str) -> float:
        """Average log-probability per bigram. Returns None if no valid bigrams."""
        if len(text) < 2:
            return None
        total_log = 0.0
        count = 0
        for i in range(len(text) - 1):
            prob = self.bigram_prob(text[i], text[i + 1])
            if prob > 1e-12:
                total_log += math.log(prob)
                count += 1
        if count == 0:
            return None
        return total_log / count

    def brand_score(self, text: str) -> float:
        if self.total_bigrams == 0:
            return 0.5
        avg_log = self._avg_log_prob(text)
        if avg_log is None:
            return 0.3 if len(text) < 2 else 0.01
        return math.exp(avg_log)

    def log_brand_score(self, text: str) -> float:
        avg_log = self._avg_log_prob(text)
        if avg_log is None:
            return -10.0
        return avg_log

    def save(self):
        with open(self._path, "wb") as f:
            pickle.dump({
                "bigram_counts": self.bigram_counts,
                "unigram_counts": self.unigram_counts,
                "total_bigrams": self.total_bigrams,
                "smoothing": self.smoothing,
            }, f, pickle.HIGHEST_PROTOCOL)
        logger.info(f"  Saved brand model ({os.path.getsize(self._path)/1024/1024:.0f}MB)")

    def load(self) -> bool:
        path = self._path
        if not os.path.exists(path):
            return False
        with open(path, "rb") as f:
            try:
                data = pickle.load(f)
            except (pickle.UnpicklingError, EOFError, AttributeError) as e:
                raise ValueError(f"Corrupted brand model: {path} ({e})") from e
        self.bigram_counts = data["bigram_counts"]
        self.unigram_counts = data["unigram_counts"]
        self.total_bigrams = data["total_bigrams"]
        self.smoothing = data.get("smoothing", data.get("smooth", 1))
        return True
