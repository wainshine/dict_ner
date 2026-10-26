"""共享 pipeline 工具函数 — org/poi 训练管线复用"""
import os
import sys
import time
import pickle
import shutil
import subprocess
from collections import Counter
from core.config import NUM_CHUNKS


def atomic_pickle_dump(obj, path: str, backup: bool = True):
    """原子写 pickle: 同目录 tmp + os.replace; 覆盖前可选 .bak 备份。

    防止 aggregate/patch 中途崩溃把现役词典写成半截文件。
    """
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    try:
        with open(tmp, "wb") as f:
            pickle.dump(obj, f)
        if backup and os.path.exists(path):
            shutil.copy2(path, path + ".bak")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def count_lines(path: str) -> int:
    n = 0
    for encoding, use_errors in (("utf-8", "strict"), ("gbk", "replace")):
        try:
            with open(path, encoding=encoding, errors=use_errors) as f:
                for _ in f:
                    n += 1
            return n
        except (FileNotFoundError, UnicodeDecodeError):
            continue
    return 0


def split_file(source: str, dest_dir: str, num_chunks: int = NUM_CHUNKS,
               source_encoding: str = "utf-8", dest_encoding: str = "utf-8",
               skip_header: bool = False) -> int:
    if not os.path.exists(source):
        raise FileNotFoundError(f"Source file not found: {source}")
    total = count_lines(source)
    per = (total + num_chunks - 1) // num_chunks  # ceil division
    print(f"Split: {total:,} lines -> {num_chunks} chunks x ~{per:,}", flush=True)
    os.makedirs(dest_dir, exist_ok=True)

    writers = [open(os.path.join(dest_dir, f"chunk_{i:02d}.csv"), "w", encoding=dest_encoding)
               for i in range(num_chunks)]
    with open(source, encoding=source_encoding, errors="replace") as f:
        if skip_header:
            next(f)
        for i, line in enumerate(f):
            chunk_id = i * num_chunks // total
            writers[chunk_id].write(line)
            if (i + 1) % 10000000 == 0:
                print(f"  {i // 10000:>4}w written", flush=True)
    for w in writers:
        w.close()
    print("  Split done", flush=True)
    return total


def clean_stats(stats_dir: str, prefix: str):
    if os.path.exists(stats_dir):
        for f in os.listdir(stats_dir):
            if f.startswith(prefix):
                os.remove(os.path.join(stats_dir, f))
    else:
        os.makedirs(stats_dir, exist_ok=True)


def launch_parallel(chunk_stats_script: str, split_dir: str, stats_dir: str,
                    output_prefix: str, extra_args: list = None, label: str = "chunk") -> bool:
    print(f"\nLaunching {NUM_CHUNKS} parallel {label} workers...", flush=True)
    t0 = time.time()
    procs = []
    os.makedirs(stats_dir, exist_ok=True)

    for i in range(NUM_CHUNKS):
        chunk = os.path.join(split_dir, f"chunk_{i:02d}.csv")
        out_pkl = os.path.join(stats_dir, f"{output_prefix}_{i:02d}.pkl")
        if not os.path.exists(chunk):
            print(f"  SKIP {label}_{i:02d}: missing", flush=True)
            continue
        cmd = [sys.executable, "-u", chunk_stats_script, chunk, out_pkl]
        if extra_args:
            cmd.extend(extra_args)
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        procs.append((i, p))
        print(f"  Started {label}_{i:02d} [pid={p.pid}]", flush=True)

    failed = []
    for i, p in procs:
        try:
            out_text = p.communicate(timeout=3600)[0]
        except subprocess.TimeoutExpired:
            p.kill()
            out_text = p.communicate()[0]
            failed.append(i)
            print(f"  [{label}_{i:02d}] TIMEOUT (killed)", flush=True)
            if out_text:
                for line in out_text.strip().split("\n")[-2:]:
                    print(f"  [{label}_{i:02d}] {line}", flush=True)
            continue
        if out_text:
            for line in out_text.strip().split("\n")[-2:]:
                print(f"  [{label}_{i:02d}] {line}", flush=True)
        if p.returncode != 0:
            failed.append(i)
            print(f"  [{label}_{i:02d}] FAILED rc={p.returncode}", flush=True)
        else:
            print(f"  [{label}_{i:02d}] done", flush=True)

    elapsed = time.time() - t0
    print(f"\n{len(procs) - len(failed)}/{len(procs)} {label}s done in {elapsed:.0f}s ({elapsed / 60:.1f}min)", flush=True)

    if failed:
        print(f"{len(failed)} chunks failed: {failed}", file=sys.stderr, flush=True)
        return False
    return True


def run_aggregate(aggregate_script: str):
    print("\nAggregating stats...", flush=True)
    subprocess.run([sys.executable, aggregate_script], check=True)


def aggregate_stats_files(stats_files: list) -> dict:
    merged = Counter()
    d1_freqs = Counter()
    d2_freqs = Counter()
    d3_freqs = Counter()
    d4_freqs = Counter()
    d4_cats = Counter()
    seg_dist = Counter()
    total = 0
    d2_hit = d3_hit = d4_hit = 0

    for path in stats_files:
        if not os.path.exists(path):
            print(f"  MISSING: {path}", flush=True)
            continue
        with open(path, "rb") as f:
            s = pickle.load(f)
        total += s["total"]
        d2_hit += s.get("d2_hit", 0)
        d3_hit += s.get("d3_hit", 0)
        d4_hit += s.get("d4_hit", 0)
        d1_freqs += s.get("d1_freqs", Counter())
        d2_freqs += s.get("d2_freqs", Counter())
        d3_freqs += s.get("d3_freqs", Counter())
        d4_freqs += s.get("d4_freqs", Counter())
        d4_cats += s.get("d4_cats", Counter())
        seg_dist += s.get("seg_dist", Counter())

    return {
        "total": total, "d2_hit": d2_hit, "d3_hit": d3_hit, "d4_hit": d4_hit,
        "d1_freqs": d1_freqs, "d2_freqs": d2_freqs,
        "d3_freqs": d3_freqs, "d4_freqs": d4_freqs,
        "d4_cats": d4_cats, "seg_dist": seg_dist,
    }


def export_d2_csv(d2_freqs: Counter, out_path: str, csv_module=None):
    if csv_module is None:
        import csv as csv_module
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv_module.writer(f)
        w.writerow(["d2_text", "freq"])
        for text, freq in d2_freqs.most_common():
            w.writerow([text, freq])
    mb = os.path.getsize(out_path) / 1024 / 1024
    print(f"  Exported d2 CSV: {out_path} ({mb:.1f}MB, {len(d2_freqs):,} unique)", flush=True)
