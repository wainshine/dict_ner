#!/usr/bin/env python3
"""全量低频序列挖掘 — seq 频次全量统计 + 模式聚类 + 词级排行榜

用法:
  python3 v3/lowfreq_mine.py scan <org|poi|loc> <chunk_csv> <out_json>
  python3 v3/lowfreq_mine.py merge <out_md> <scan1.json> [scan2.json ...] [--threshold 3]

scan: 单 chunk 全量, 输出 seq_counts + 每 seq 最多3条样例 (name, [seg texts])
merge: 合并计数 → 低频 (count<=threshold) 模式聚类 + 词级排行榜 → MD 报告
"""
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import SegType, LEVEL_ORDER

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ADMIN_TYPES = {SegType.PROVINCE, SegType.CITY, SegType.DISTRICT, SegType.TOWN,
               SegType.VILLAGE, SegType.COMMUNITY, SegType.ROAD}
NON_ADMIN = {SegType.BRAND, SegType.INDUSTRY, SegType.POI, SegType.ORG_SUFFIX}


def build_engine(system):
    from v3.engine.configs import build_org_engine, build_poi_engine, build_loc_engine
    if system == "org":
        return build_org_engine("v1.5.0")
    if system == "poi":
        return build_poi_engine("poi_v1.5.0.pkl")
    return build_loc_engine("loc_v1.5.0")


def scan(system, chunk_path, out_path):
    eng = build_engine(system)
    seq_counts = Counter()
    seq_examples = {}
    total = 0
    with open(chunk_path, encoding="utf-8") as f:
        for line in f:
            name = line.rstrip("\n").split("\t")[0].split(",")[0].strip()
            if len(name) < 2:
                continue
            total += 1
            res = eng.recognize(name)
            key = " ".join(s.seg_type.value for s in res.segments)
            seq_counts[key] += 1
            if key in seq_examples or len(seq_examples) < 300000:
                if len(seq_examples.get(key, [])) < 3:
                    seq_examples.setdefault(key, []).append(
                        [name, [s.text for s in res.segments]])
            if total % 2000000 == 0:
                print(f"  [{system}] {total:,}", flush=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"system": system, "total": total,
                   "seq_counts": dict(seq_counts),
                   "seq_examples": seq_examples}, f, ensure_ascii=False)
    print(f"[{system}] {os.path.basename(chunk_path)} DONE total={total:,} "
          f"distinct={len(seq_counts):,}", flush=True)


# ---------- merge 侧: 模式分类 (全类型) ----------

def _lv(t):
    return LEVEL_ORDER.get(SegType(t), 99)


def classify_patterns(types):
    """types: tuple of type-value strings → 命中的模式集合"""
    flags = set()
    n = len(types)
    tset = [SegType(t) for t in types]

    # 行政逆序/后置
    admin_lv = [_lv(t) for t in types if SegType(t) in ADMIN_TYPES]
    for i in range(1, len(admin_lv)):
        if admin_lv[i] < admin_lv[i - 1]:
            flags.add("行政逆序")
            break
    seen_non = False
    for t in tset:
        if t in NON_ADMIN:
            seen_non = True
        elif t in ADMIN_TYPES and seen_non:
            flags.add("行政后置")
            break

    # BRAND 连碎 (≥3 连续 BRAND)
    run = 1
    for i in range(1, n):
        run = run + 1 if types[i] == types[i - 1] else 1
        if types[i] == "BRAND" and run >= 3:
            flags.add("BRAND连碎≥3")
            break
    # POI 连缀 (≥3 连续 POI)
    run = 1
    for i in range(1, n):
        run = run + 1 if types[i] == types[i - 1] else 1
        if types[i] == "POI" and run >= 3:
            flags.add("POI连缀≥3")
            break
    # INDUSTRY 连缀 (≥2)
    for i in range(1, n):
        if types[i] == "INDUSTRY" and types[i - 1] == "INDUSTRY":
            flags.add("INDUSTRY连缀")
            break
    # 类型横跳 A→B→A (A∈BRAND/INDUSTRY/POI, B≠A)
    for i in range(2, n):
        if types[i] == types[i - 2] and types[i] != types[i - 1] \
                and types[i] in ("BRAND", "INDUSTRY", "POI"):
            flags.add("类型横跳")
            break
    # 中段 UNKNOWN
    if "UNKNOWN" in types[1:-1]:
        flags.add("中段UNKNOWN")
    return flags


def merge(out_md, paths, threshold):
    counts = Counter()
    examples = {}
    system = None
    total = 0
    for p in paths:
        r = json.load(open(p, encoding="utf-8"))
        system = system or r["system"]
        total += r["total"]
        counts.update(r["seq_counts"])
        for k, v in r["seq_examples"].items():
            if k not in examples:
                examples[k] = v

    low = {k: c for k, c in counts.items() if c <= threshold}
    patterns = defaultdict(lambda: {"count": 0, "seqs": 0, "examples": []})
    word_board = Counter()  # (word, seg_type, pos) in lowfreq seqs
    for seq, c in low.items():
        types = tuple(seq.split(" "))
        flags = classify_patterns(types) or {"无模式(长尾)"}
        for fl in flags:
            patterns[fl]["count"] += c
            patterns[fl]["seqs"] += 1
            if len(patterns[fl]["examples"]) < 10:
                for name, segs in examples.get(seq, [])[:2]:
                    patterns[fl]["examples"].append([name, list(zip(segs, types))])
        ex = examples.get(seq, [])
        segs = ex[0][1] if ex else [""] * len(types)
        for i, t in enumerate(types):
            pos = "首" if i == 0 else ("尾" if i == len(types) - 1 else "中")
            w = segs[i] if i < len(segs) else ""
            word_board[(w, t, pos)] += c

    lines = [f"# 全量低频序列挖掘 ({system}, {total:,} 条)", "",
             f"- 结构种类 {len(counts):,}",
             f"- 低频 (count≤{threshold}): {len(low):,} 种 / "
             f"{sum(low.values()):,} 条 ({100*sum(low.values())/max(1,total):.2f}%)", "",
             "## 模式聚类", "",
             "| 模式 | 序列种数 | 条数 | 占全量 |",
             "|------|--------:|-----:|-----:|"]
    for fl, v in sorted(patterns.items(), key=lambda kv: -kv[1]["count"]):
        lines.append(f"| {fl} | {v['seqs']:,} | {v['count']:,} | "
                     f"{100*v['count']/max(1,total):.3f}% |")
    lines.append("")
    for fl, v in sorted(patterns.items(), key=lambda kv: -kv[1]["count"]):
        lines.append(f"### {fl} ({v['seqs']:,} 种, {v['count']:,} 条)")
        lines.append("")
        for name, pairs in v["examples"][:8]:
            seg_str = " | ".join(f"[{t}]{w}" for w, t in pairs)
            lines.append(f"- `{name}` — {seg_str}")
        lines.append("")

    lines += ["## 词级排行榜 (低频序列内, 词×类型×位置 Top 100)", "",
              "| 词 | 类型 | 位置 | 条数 |",
              "|----|------|------|-----:|"]
    for (w, t, pos), c in word_board.most_common(100):
        lines.append(f"| {w} | {t} | {pos} | {c:,} |")
    lines.append("")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"report: {out_md}")
    print(f"lowfreq: {len(low):,} seqs / {sum(low.values()):,} rows")


def main():
    cmd = sys.argv[1]
    if cmd == "scan":
        scan(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "merge":
        threshold = 3
        args = sys.argv[3:]
        if "--threshold" in args:
            i = args.index("--threshold")
            threshold = int(args[i + 1])
            args = args[:i] + args[i + 2:]
        merge(sys.argv[2], args, threshold)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
