#!/usr/bin/env python3
"""全量段对比 launcher — 16进程并行, 产出 output/v3_seg_compare_report.md

用法:
  python v3/seg_compare.py run <org|poi|loc>   # 16进程跑全量
  python v3/seg_compare.py report               # 汇总报告
"""
import glob
import json
import os
import subprocess
import sys
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
OUT_DIR = os.path.join(BASE, "output", "v3_seg_compare")
NUM_CHUNKS = 16


def run(system):
    mode = sys.argv[3] if len(sys.argv) > 3 else "legacy_vs_v130"
    os.makedirs(OUT_DIR, exist_ok=True)
    worker = os.path.join(BASE, "v3", "seg_compare_worker.py")
    suffix = "_v140" if mode == "v130_vs_v140" else ""
    procs = []
    for i in range(NUM_CHUNKS):
        chunk = os.path.join(DATA, "split", system, f"chunk_{i:02d}.csv")
        if not os.path.exists(chunk):
            continue
        out = os.path.join(OUT_DIR, f"{system}{suffix}_{i:02d}.json")
        log = os.path.join(OUT_DIR, f"{system}{suffix}_{i:02d}.log")
        with open(log, "w") as lf:
            p = subprocess.Popen([sys.executable, worker, system, chunk, out, mode],
                                 stdout=lf, stderr=subprocess.STDOUT)
        procs.append((i, p))
    print(f"[{system}] launched {len(procs)} workers")
    failed = [i for i, p in procs if p.wait() != 0]
    print(f"[{system}] done, failed: {failed or 'none'}", flush=True)
    return not failed


def report():
    lines = ["# v1.2.3 → v1.3.0 全量段对比报告", ""]
    for system in ("org", "poi", "loc"):
        pat = sys.argv[2] if len(sys.argv) > 2 else "{system}_*.json"
        files = sorted(glob.glob(os.path.join(OUT_DIR, pat.format(system=system))))
        if not files:
            continue
        total = diff = 0
        type_old, type_new = Counter(), Counter()
        examples = []
        for fp in files:
            with open(fp, encoding="utf-8") as f:
                r = json.load(f)
            total += r["total"]
            diff += r["diff"]
            type_old.update(r["type_old"])
            type_new.update(r["type_new"])
            examples.extend(r["examples"][:5])
        lines += [f"## {system.upper()} ({total:,} 条)", "",
                  f"- 段文本差异: **{diff:,} ({100*diff/max(1,total):.2f}%)**", "",
                  "| 段类型 | v1.2.3 | v1.3.0 | 差异 |", "|------|-------:|-------:|-----:|"]
        for t in sorted(set(type_old) | set(type_new)):
            o, n = type_old.get(t, 0), type_new.get(t, 0)
            lines.append(f"| {t} | {o:,} | {n:,} | {n-o:+,} |")
        lines += ["", "### 差异样例", ""]
        for name, so, sn in examples[:10]:
            lines.append(f"- 「{name}」")
            lines.append(f"  - 旧: {so}")
            lines.append(f"  - 新: {sn}")
        lines.append("")
    path = os.path.join(OUT_DIR, "..", "v3_seg_compare_report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines[:40]))
    print(f"\nreport: {path}")


def main():
    cmd = sys.argv[1]
    if cmd == "run":
        ok = run(sys.argv[2])
        sys.exit(0 if ok else 1)
    elif cmd == "report":
        report()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
