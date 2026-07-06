#!/usr/bin/env python3
"""POI V1 launch — filter + split + 16 parallel chunk stats + aggregate"""
import os, sys, time, subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import BASE_DIR, DATA_DIR, DICT_DIR, VERSION, NUM_CHUNKS
from tools.pipeline_base import count_lines, split_file, launch_parallel, run_aggregate, clean_stats

POI_A = os.path.join(DATA_DIR, "兴趣点A（6500w）input.txt")
POI_T = os.path.join(DATA_DIR, "兴趣点T（7200w）input.txt")
CLEANED = os.path.join(DATA_DIR, "poi_deduped.txt")
SPLIT_DIR = os.path.join(DATA_DIR, "split/poi")

FILTER = os.path.join(BASE_DIR, "tools", "poi_dedup.py")
CHUNK_STATS = os.path.join(BASE_DIR, "tools", "poi_chunk_stats.py")
AGGREGATE = os.path.join(BASE_DIR, "tools", "poi_aggregate.py")


def cmd_dedup():
    print(f"Deduping A+T → {CLEANED}")
    subprocess.run([sys.executable, FILTER, CLEANED, POI_A, POI_T], check=True)
    total = count_lines(CLEANED)
    mb = os.path.getsize(CLEANED) / 1024 / 1024
    print(f"Deduped POI: {total:,} unique, {mb:.0f}MB")


def cmd_split():
    split_file(CLEANED, SPLIT_DIR, NUM_CHUNKS)


def cmd_stats():
    stats_dir = os.path.join(DICT_DIR, f"iter_{VERSION}")
    ok = launch_parallel(CHUNK_STATS, SPLIT_DIR, stats_dir, "poi_stats", label="poi")
    if not ok:
        sys.exit(1)


def _check_sources():
    missing = []
    for path in (POI_A, POI_T):
        if not os.path.exists(path):
            missing.append(path)
    if missing:
        print(f"ERROR: POI source file(s) not found. Cannot rebuild chunks.")
        for m in missing:
            print(f"  Missing: {m}")
        print(f"  To restore chunks without rebuilding: copy from backup to {SPLIT_DIR}/")
        sys.exit(1)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    chunks_exist = os.path.exists(os.path.join(SPLIT_DIR, "chunk_00.csv"))

    if cmd in ("filter", "dedup"):
        cmd_dedup()
    if cmd in ("split"):
        cmd_split()
    if cmd == "all":
        if chunks_exist:
            print(f"Split chunks exist at {SPLIT_DIR}, skipping dedup+split")
        else:
            _check_sources()
            cmd_dedup()
            cmd_split()
    if cmd in ("clean", "all"):
        clean_stats(os.path.join(DICT_DIR, f"iter_{VERSION}"), "poi_stats_")
    if cmd in ("stats", "all"):
        cmd_stats()
    if cmd in ("agg", "all"):
        run_aggregate(AGGREGATE)


if __name__ == "__main__":
    main()
