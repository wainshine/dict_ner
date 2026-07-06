#!/usr/bin/env python3
"""org V6 launch — re-split + 16 parallel chunk stats + aggregate"""
import os, sys, time, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import BASE_DIR, DATA_DIR, DICT_DIR, VERSION, NUM_CHUNKS
from tools.pipeline_base import count_lines, split_file, launch_parallel, run_aggregate, clean_stats

SOURCE = os.path.join(DATA_DIR, "org_corpus.csv")
SPLIT_DIR = os.path.join(DATA_DIR, "split/org")
CHUNK_STATS = os.path.join(BASE_DIR, "tools", "org_chunk_stats.py")
AGGREGATE = os.path.join(BASE_DIR, "tools", "org_aggregate.py")


def re_split():
    split_file(SOURCE, SPLIT_DIR, NUM_CHUNKS, source_encoding="gbk", skip_header=True)


def run_parallel():
    stats_dir = os.path.join(DICT_DIR, f"iter_{VERSION}")
    ok = launch_parallel(CHUNK_STATS, SPLIT_DIR, stats_dir, "org_stats", label="org")
    if not ok:
        sys.exit(1)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("split", "all"):
        re_split()
    if cmd in ("clean", "all"):
        clean_stats(os.path.join(DICT_DIR, f"iter_{VERSION}"), "org_stats_")
    if cmd in ("stats", "all"):
        run_parallel()
    if cmd in ("agg", "all"):
        run_aggregate(AGGREGATE)


if __name__ == "__main__":
    main()
