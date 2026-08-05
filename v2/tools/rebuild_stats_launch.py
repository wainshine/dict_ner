#!/usr/bin/env python3
"""Rebuild stats for existing eval outputs — 16 parallel per version"""
import os, sys, subprocess

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKER = os.path.join(BASE, "v2", "tools", "rebuild_stats_worker.py")

dirs = [
    ("output/org_eval", ["org_v1.1.3", "org_v1.2.0", "org_v1.2.2"]),
    ("output/poi_eval", ["poi_v1.1.3", "poi_v1.2.0", "poi_v1.2.2"]),
    ("output/loc_eval", ["loc_v1.1.3", "loc_v1.2.1", "loc_v1.2.2"]),
]

for base, versions in dirs:
    for ver in versions:
        ver_dir = os.path.join(BASE, base, ver)
        if not os.path.isdir(ver_dir):
            print(f"SKIP missing: {ver_dir}", flush=True)
            continue
        print(f"\n{ver_dir}", flush=True)
        procs = []
        for chunk_name in sorted(os.listdir(ver_dir)):
            if not chunk_name.endswith(".jsonl"):
                continue
            jpath = os.path.join(ver_dir, chunk_name)
            p = subprocess.Popen(
                [sys.executable, "-u", WORKER, jpath],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
            procs.append((chunk_name, p))

        for chunk_name, p in procs:
            out = p.communicate(timeout=300)[0]
            if out:
                print(out.strip(), flush=True)
print("\ndone", flush=True)
