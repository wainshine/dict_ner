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
    with open(in_csv, encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header, data = rows[0], rows[1:]
    per = (len(data) + NUM_CHUNKS - 1) // NUM_CHUNKS
    for i in range(NUM_CHUNKS):
        part = data[i * per:(i + 1) * per]
        if not part:
            continue
        with open(os.path.join(CHUNK_DIR, f"chunk_{i:02d}.csv"), "w",
                  encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(part)
    print(f"Split {len(data):,} rows -> {CHUNK_DIR} ({NUM_CHUNKS} chunks)")


def run():
    os.makedirs(FEAT_DIR, exist_ok=True)
    worker = os.path.join(BASE, "v3", "precompute_worker.py")
    chunks = sorted(glob.glob(os.path.join(CHUNK_DIR, "chunk_*.csv")))
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
    feats = sorted(glob.glob(os.path.join(FEAT_DIR, "chunk_*.csv")))
    total = 0
    with open(out_csv, "w", encoding="utf-8", newline="") as fout:
        w = None
        for i, fp in enumerate(feats):
            with open(fp, encoding="utf-8") as f:
                r = csv.reader(f)
                header = next(r)
                if w is None:
                    w = csv.writer(fout)
                    w.writerow(header)
                for row in r:
                    w.writerow(row)
                    total += 1
    print(f"Merged {len(feats)} chunks -> {out_csv} ({total:,} rows)")


def main():
    cmd = sys.argv[1]
    if cmd == "split":
        split(sys.argv[2])
    elif cmd == "run":
        ok = run()
        sys.exit(0 if ok else 1)
    elif cmd == "merge":
        merge(sys.argv[2])
    elif cmd == "all":
        split(sys.argv[2])
        if run():
            merge(sys.argv[3])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
