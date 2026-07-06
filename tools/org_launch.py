#!/usr/bin/env python3
"""org16kw V6 launch — re-split + 16 parallel chunk stats + aggregate"""

import os, sys, time, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "data")
DICT_DIR = os.path.join(BASE, "dicts")
VERSION = "v1.1.1"
NUM_CHUNKS = 16
SOURCE = os.path.join(DATA_DIR, "org_corpus.csv")
SPLIT_DIR = os.path.join(DATA_DIR, "split/org")
CHUNK_STATS = os.path.join(BASE, "tools", "org_chunk_stats.py")
AGGREGATE = os.path.join(BASE, "tools", "org_aggregate.py")


def count_lines(path):
    n = 0
    with open(path, encoding="gbk", errors="replace") as f:
        for _ in f:
            n += 1
    return n


def re_split():
    total = count_lines(SOURCE)
    per = total // NUM_CHUNKS + 1
    print(f"Split org16kw: {total:,} total → ~{per:,} per chunk")
    os.makedirs(SPLIT_DIR, exist_ok=True)

    writers = [open(os.path.join(SPLIT_DIR, f"chunk_{i:02d}.csv"), "w", encoding="utf-8")
               for i in range(NUM_CHUNKS)]
    with open(SOURCE, encoding="gbk", errors="replace") as f:
        next(f)
        for i, line in enumerate(f):
            chunk_id = min(i // per, NUM_CHUNKS - 1)
            writers[chunk_id].write(line)
            if (i + 1) % 20000000 == 0:
                print(f"  {i // 10000:>4}w written")
    for w in writers:
        w.close()
    print("  Split done")


def clean_old_stats():
    for i in range(NUM_CHUNKS):
        p = os.path.join(DICT_DIR, f"org_stats_{VERSION}_{i:02d}.pkl")
        if os.path.exists(p):
            os.remove(p)


def run_parallel():
    print(f"\nLaunching {NUM_CHUNKS} parallel workers...")
    t0 = time.time()
    procs = []
    for i in range(NUM_CHUNKS):
        chunk = os.path.join(SPLIT_DIR, f"chunk_{i:02d}.csv")
        stats_dir = os.path.join(DICT_DIR, f"iter_{VERSION}")
        os.makedirs(stats_dir, exist_ok=True)
        out = os.path.join(stats_dir, f"org_stats_{i:02d}.pkl")
        if not os.path.exists(chunk):
            print(f"  SKIP chunk_{i:02d}: missing")
            continue
        p = subprocess.Popen(
            [sys.executable, "-u", CHUNK_STATS, chunk, out],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        procs.append((i, p))
        print(f"  Started chunk_{i:02d} [pid={p.pid}]")

    for i, p in procs:
        out_text = p.communicate()[0]
        if out_text:
            for line in out_text.strip().split("\n")[-2:]:
                print(f"  [chunk_{i:02d}] {line}")
        print(f"  chunk_{i:02d} done [rc={p.returncode}]")

    elapsed = time.time() - t0
    print(f"\nAll {len(procs)} chunks done in {elapsed:.0f}s ({elapsed/60:.1f}min)")


def run_aggregate():
    print("\nAggregating stats...")
    subprocess.run([sys.executable, AGGREGATE], check=True)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("split", "all"):
        re_split()
    if cmd in ("clean", "all"):
        clean_old_stats()
    if cmd in ("stats", "all"):
        run_parallel()
    if cmd in ("agg", "all"):
        run_aggregate()


if __name__ == "__main__":
    main()
