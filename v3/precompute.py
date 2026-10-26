#!/usr/bin/env python3
"""特征预计算 launcher — 16进程并行 (沿用项目 bash & 模式)

用法:
  python v3/precompute.py split <in_csv>          # 切成16个chunk → output/v3_feat/chunks/
  python v3/precompute.py run                     # 16进程并行跑 worker
  python v3/precompute.py merge <out_csv>         # 合并chunk特征 → 单文件
  python v3/precompute.py all <in_csv> <out_csv>  # split+run+merge
"""
import csv
import glob
import os
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK_DIR = os.path.join(BASE, "output", "v3_feat")
CHUNK_DIR = os.path.join(WORK_DIR, "chunks")
FEAT_DIR = os.path.join(WORK_DIR, "feats")
NUM_CHUNKS = 16


def split(in_csv):
    os.makedirs(CHUNK_DIR, exist_ok=True)
    for old in glob.glob(os.path.join(CHUNK_DIR, "chunk_*.csv")):
        os.remove(old)
    writers = []
    writer_objs = []
    try:
        with open(in_csv, encoding="utf-8", newline="") as f:
            r = csv.reader(f)
            try:
                header = next(r)
            except StopIteration:
                raise SystemExit(f"empty input: {in_csv}")
            for i in range(NUM_CHUNKS):
                path = os.path.join(CHUNK_DIR, f"chunk_{i:02d}.csv")
                fout = open(path, "w", encoding="utf-8", newline="")
                writers.append(fout)
                writer = csv.writer(fout)
                writer.writerow(header)
                writer_objs.append(writer)
            total = 0
            for i, row in enumerate(r):
                writer_objs[i % NUM_CHUNKS].writerow(row)
                total += 1
    finally:
        for fout in writers:
            fout.close()
    print(f"Split {total:,} rows -> {CHUNK_DIR} ({NUM_CHUNKS} chunks)")


def run():
    os.makedirs(FEAT_DIR, exist_ok=True)
    worker = os.path.join(BASE, "v3", "precompute_worker.py")
    chunks = sorted(glob.glob(os.path.join(CHUNK_DIR, "chunk_*.csv")))
    if not chunks:
        print(f"No chunks in {CHUNK_DIR}; run 'precompute.py split <in_csv>' first")
        return False
    # 确认有 chunk 后再清上一轮特征, 避免误删有效产物
    for old in (glob.glob(os.path.join(FEAT_DIR, "chunk_*.csv"))
                + glob.glob(os.path.join(FEAT_DIR, "chunk_*.log"))):
        os.remove(old)
    procs = []
    t0 = time.time()
    for c in chunks:
        name = os.path.basename(c)
        out = os.path.join(FEAT_DIR, name)
        log = os.path.join(FEAT_DIR, name.replace(".csv", ".log"))
        with open(log, "w") as lf:
            p = subprocess.Popen([sys.executable, worker, c, out],
                                 stdout=lf, stderr=subprocess.STDOUT)
        procs.append((name, p))
    print(f"Launched {len(procs)} workers")
    failed = []
    for name, p in procs:
        p.wait()
        if p.returncode != 0:
            failed.append(name)
    print(f"All workers done in {time.time()-t0:.0f}s, failed: {failed or 'none'}")
    return not failed


def merge(out_csv):
    expected = sorted(glob.glob(os.path.join(CHUNK_DIR, "chunk_*.csv")))
    if not expected:
        raise SystemExit(f"No chunks in {CHUNK_DIR}; run 'precompute.py split <in_csv>' first")
    feats = []
    missing = []
    for c in expected:
        fp = os.path.join(FEAT_DIR, os.path.basename(c))
        if os.path.exists(fp):
            feats.append(fp)
        else:
            missing.append(os.path.basename(c))
    if missing:
        raise SystemExit(f"Missing feature chunks: {missing}; rerun 'precompute.py run'")
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    total = 0
    header0 = None
    counts = []
    with open(out_csv, "w", encoding="utf-8", newline="") as fout:
        w = None
        for i, fp in enumerate(feats):
            with open(fp, encoding="utf-8") as f:
                r = csv.reader(f)
                header = next(r)
                if header0 is None:
                    header0 = header
                    w = csv.writer(fout)
                    w.writerow(header)
                elif header != header0:
                    raise SystemExit(f"header mismatch in {fp}")
                n = 0
                for row in r:
                    w.writerow(row)
                    total += 1
                    n += 1
                counts.append(n)
    print(f"Merged {len(feats)} chunks -> {out_csv} ({total:,} rows; per-chunk={counts})")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "split":
        if len(sys.argv) < 3:
            raise SystemExit("usage: precompute.py split <in_csv>")
        split(sys.argv[2])
    elif cmd == "run":
        ok = run()
        sys.exit(0 if ok else 1)
    elif cmd == "merge":
        if len(sys.argv) < 3:
            raise SystemExit("usage: precompute.py merge <out_csv>")
        merge(sys.argv[2])
    elif cmd == "all":
        if len(sys.argv) < 4:
            raise SystemExit("usage: precompute.py all <in_csv> <out_csv>")
        split(sys.argv[2])
        if run():
            merge(sys.argv[3])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
