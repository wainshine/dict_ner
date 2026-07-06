#!/usr/bin/env python3
"""POI V1 launch — filter + split + 16 parallel chunk stats + aggregate"""
import os, sys, time, subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "data")
DICT_DIR = os.path.join(BASE, "dicts")
VERSION = "v1.1.1"
NUM_CHUNKS = 16

POI_A = os.path.join(DATA_DIR, "兴趣点A（6500w）input.txt")
POI_T = os.path.join(DATA_DIR, "兴趣点T（7200w）input.txt")
CLEANED = os.path.join(DATA_DIR, "poi_deduped.txt")
SPLIT_DIR = os.path.join(DATA_DIR, "split/poi")

FILTER = os.path.join(BASE, "tools", "poi_dedup.py")
CHUNK_STATS = os.path.join(BASE, "tools", "poi_chunk_stats.py")
AGGREGATE = os.path.join(BASE, "tools", "poi_aggregate.py")


def count_lines(path):
    n = 0
    try:
        with open(path, encoding='utf-8') as f:
            for _ in f:
                n += 1
    except (UnicodeDecodeError, FileNotFoundError):
        with open(path, encoding='gbk', errors='replace') as f:
            for _ in f:
                n += 1
    return n


def cmd_dedup():
    """Dedup A+T, writing frequency-weighted output."""
    print(f"Deduping A+T → {CLEANED}")
    subprocess.run([sys.executable, FILTER, CLEANED, POI_A, POI_T], check=True)
    total = count_lines(CLEANED)
    mb = os.path.getsize(CLEANED) / 1024 / 1024
    print(f"Deduped POI: {total:,} unique, {mb:.0f}MB")


def cmd_split():
    total = count_lines(CLEANED)
    per = total // NUM_CHUNKS + 1
    print(f"Split POI: {total:,} → {NUM_CHUNKS} chunks × ~{per:,}")
    os.makedirs(SPLIT_DIR, exist_ok=True)

    writers = [open(os.path.join(SPLIT_DIR, f"chunk_{i:02d}.csv"), "w", encoding="utf-8")
               for i in range(NUM_CHUNKS)]
    with open(CLEANED, encoding="utf-8") as f:
        for i, line in enumerate(f):
            chunk_id = min(i // per, NUM_CHUNKS - 1)
            writers[chunk_id].write(line)
            if (i + 1) % 10000000 == 0:
                print(f"  {i//10000:>4}w written")
    for w in writers:
        w.close()
    print("  Split done")


def cmd_clean():
    stats_dir = os.path.join(DICT_DIR, f"iter_{VERSION}")
    if os.path.exists(stats_dir):
        for f in os.listdir(stats_dir):
            if f.startswith("poi_stats_"):
                os.remove(os.path.join(stats_dir, f))
    else:
        os.makedirs(stats_dir, exist_ok=True)


def cmd_stats():
    print(f"\nLaunching {NUM_CHUNKS} parallel POI workers...")
    t0 = time.time()
    procs = []
    for i in range(NUM_CHUNKS):
        chunk = os.path.join(SPLIT_DIR, f"chunk_{i:02d}.csv")
        stats_dir = os.path.join(DICT_DIR, f"iter_{VERSION}")
        os.makedirs(stats_dir, exist_ok=True)
        out_pkl = os.path.join(stats_dir, f"poi_stats_{i:02d}.pkl")
        if not os.path.exists(chunk):
            print(f"  SKIP chunk_{i:02d}: missing")
            continue
        p = subprocess.Popen(
            [sys.executable, "-u", CHUNK_STATS, chunk, out_pkl, "poi_v1.7"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        procs.append((i, p))

    for i, p in procs:
        out_text = p.communicate()[0]
        if out_text:
            for line in out_text.strip().split("\n")[-2:]:
                print(f"  [chunk_{i:02d}] {line.strip()}")
        print(f"  chunk_{i:02d} done [rc={p.returncode}]")

    elapsed = time.time() - t0
    print(f"\nAll {len(procs)} chunks done in {elapsed:.0f}s ({elapsed/60:.1f}min)")


def cmd_agg():
    print("\nAggregating POI stats...")
    subprocess.run([sys.executable, AGGREGATE], check=True)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("filter", "dedup", "all"):
        cmd_dedup()
    if cmd in ("split", "all"):
        cmd_split()
    if cmd in ("clean", "all"):
        cmd_clean()
    if cmd in ("stats", "all"):
        cmd_stats()
    if cmd in ("agg", "all"):
        cmd_agg()


if __name__ == "__main__":
    main()
