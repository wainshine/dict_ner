#!/usr/bin/env python3
"""v1.3.0 eval 重切 launcher — 16进程并行

用法: python v3/eval_cut.py run <org|poi|loc>
产出: output/{system}_eval/{system}_v1.3.0/chunk_XX.jsonl + chunk_XX_stats.json
"""
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
NUM_CHUNKS = 16


def run(system, version="v1.3.0"):
    out_dir = os.path.join(BASE, "output", f"{system}_eval", f"{system}_{version}")
    os.makedirs(out_dir, exist_ok=True)
    worker = os.path.join(BASE, "v3", "eval_cut_worker.py")
    procs = []
    for i in range(NUM_CHUNKS):
        chunk = os.path.join(DATA, "split", system, f"chunk_{i:02d}.csv")
        if not os.path.exists(chunk):
            continue
        jsonl = os.path.join(out_dir, f"chunk_{i:02d}.jsonl")
        stats = os.path.join(out_dir, f"chunk_{i:02d}_stats.json")
        log = os.path.join(out_dir, f"chunk_{i:02d}.log")
        with open(log, "w") as lf:
            p = subprocess.Popen([sys.executable, worker, system, chunk, jsonl, stats,
                                  version],
                                 stdout=lf, stderr=subprocess.STDOUT)
        procs.append((i, p))
    print(f"[{system}] launched {len(procs)} workers", flush=True)
    failed = [i for i, p in procs if p.wait() != 0]
    print(f"[{system}] done, failed: {failed or 'none'}", flush=True)
    return not failed


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "run":
        ok = run(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "v1.3.0")
        sys.exit(0 if ok else 1)
    print(__doc__)
    sys.exit(1)


if __name__ == "__main__":
    main()
