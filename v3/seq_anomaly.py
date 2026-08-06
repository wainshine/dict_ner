#!/usr/bin/env python3
"""结构异常挖掘 — 行政层级逆序/行政后置检测 (seq 结构规则 × 低频)

用法:
  python3 v3/seq_anomaly.py scan <org|poi|loc> <chunk_csv> <n> <out_json>
  python3 v3/seq_anomaly.py report <scan1.json> [scan2.json ...]

规则:
  R1 行政逆序: 行政段子序列中, 后出现更高层级 (LEVEL_ORDER 值更小)
  R2 行政后置: 行政段出现在非行政段 (BRAND/INDUSTRY/POI/ORG_SUFFIX) 之后
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import SegType, LEVEL_ORDER

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_MD = os.path.join(BASE, "output", "v4_seq_anomaly.md")

ADMIN_TYPES = {SegType.PROVINCE, SegType.CITY, SegType.DISTRICT, SegType.TOWN,
               SegType.VILLAGE, SegType.COMMUNITY, SegType.ROAD}
NON_ADMIN = {SegType.BRAND, SegType.INDUSTRY, SegType.POI, SegType.ORG_SUFFIX}


def classify_anomaly(types):
    """返回异常标记集合 (空 = 正常)"""
    flags = set()
    admin_lv = [LEVEL_ORDER.get(t, 99) for t in types if t in ADMIN_TYPES]
    # R1: 行政逆序 (后出现的行政段层级更高)
    for i in range(1, len(admin_lv)):
        if admin_lv[i] < admin_lv[i - 1]:
            flags.add("R1_行政逆序")
            break
    # R2: 行政段跟非行政段之后
    seen_non_admin = False
    for t in types:
        if t in NON_ADMIN:
            seen_non_admin = True
        elif t in ADMIN_TYPES and seen_non_admin:
            flags.add("R2_行政后置")
            break
    return flags


def scan(system, chunk_path, n, out_path):
    from v3.engine.configs import build_org_engine, build_poi_engine, build_loc_engine
    if system == "org":
        eng = build_org_engine("v1.5.0")
    elif system == "poi":
        eng = build_poi_engine("poi_v1.5.0.pkl")
    else:
        eng = build_loc_engine("loc_v1.5.0")

    seq_counts = Counter()
    seq_example = {}
    anomaly = defaultdict(lambda: [0, []])  # flag -> [count, examples]
    total = 0
    with open(chunk_path, encoding="utf-8") as f:
        for line in f:
            name = line.rstrip("\n").split("\t")[0].split(",")[0].strip()
            if len(name) < 2:
                continue
            total += 1
            if total > n:
                break
            res = eng.recognize(name)
            types = tuple(s.seg_type for s in res.segments)
            key = " → ".join(t.value for t in types)
            seq_counts[key] += 1
            seq_example.setdefault(key, name)
            for fl in classify_anomaly(types):
                anomaly[fl][0] += 1
                if len(anomaly[fl][1]) < 30:
                    anomaly[fl][1].append([name, key])

    out = {
        "system": system, "chunk": os.path.basename(chunk_path), "total": total,
        "n_distinct_seq": len(seq_counts),
        "n_singleton": sum(1 for c in seq_counts.values() if c == 1),
        "anomaly": {k: {"count": v[0], "examples": v[1]} for k, v in anomaly.items()},
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"[{system}] total={total:,} distinct_seq={len(seq_counts):,} "
          f"singleton={out['n_singleton']:,} "
          f"anomaly={ {k: v['count'] for k, v in out['anomaly'].items()} }", flush=True)


def report(paths):
    lines = ["# 结构异常挖掘报告 (v1.5.0 现役引擎, 20万抽样/体系)", ""]
    for p in paths:
        r = json.load(open(p, encoding="utf-8"))
        lines += [f"## {r['system']} ({r['chunk']}, {r['total']:,} 条)", "",
                  f"- 结构种类 {r['n_distinct_seq']:,}, 单例(出现1次) {r['n_singleton']:,} "
                  f"({100*r['n_singleton']/max(1,r['n_distinct_seq']):.0f}%)", ""]
        for flag, v in sorted(r["anomaly"].items(), key=lambda kv: -kv[1]["count"]):
            rate = 100 * v["count"] / max(1, r["total"])
            lines.append(f"### {flag}: {v['count']:,} 条 ({rate:.2f}%)")
            lines.append("")
            for name, seq in v["examples"][:15]:
                lines.append(f"- `{name}` — {seq}")
            lines.append("")
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"report: {OUT_MD}")


def main():
    cmd = sys.argv[1]
    if cmd == "scan":
        scan(sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5])
    elif cmd == "report":
        report(sys.argv[2:])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
