#!/usr/bin/env python3
"""两版本 ORG 全量识别 → 评估报告 (训练语料 data/split/org/)"""
import os, sys, time, json, subprocess
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(BASE, "output", "org_eval")
WORKER = os.path.join(BASE, "tools", "org_eval_worker.py")
SPLIT_DIR = os.path.join(BASE, "data", "split", "org")
NUM_CHUNKS = 16
VERSIONS = ["v1.1.3", "v1.2.0", "v1.2.2", "v1.2.3"]

os.makedirs(OUT_DIR, exist_ok=True)


def run_version(version):
    out_ver = os.path.join(OUT_DIR, f"org_{version}")
    os.makedirs(out_ver, exist_ok=True)

    first_jsonl = os.path.join(out_ver, "chunk_00.jsonl")
    if os.path.exists(first_jsonl):
        print(f"  {version}: already done, skipping", flush=True)
        return

    t0 = time.time()
    procs = []
    for i in range(NUM_CHUNKS):
        chunk = os.path.join(SPLIT_DIR, f"chunk_{i:02d}.csv")
        out_jsonl = os.path.join(out_ver, f"chunk_{i:02d}.jsonl")
        if not os.path.exists(chunk):
            print(f"  SKIP chunk_{i:02d}: missing", flush=True)
            continue
        p = subprocess.Popen(
            [sys.executable, "-u", WORKER, chunk, out_jsonl, version],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        procs.append((i, p))

    for i, p in procs:
        out_text = p.communicate(timeout=7200)[0]
        if out_text:
            for line in out_text.strip().split("\n")[-2:]:
                print(f"  [{version} chunk_{i:02d}] {line}", flush=True)
    elapsed = time.time() - t0
    print(f"  {version}: {len(procs)} chunks done in {elapsed:.0f}s ({elapsed/60:.1f}min)", flush=True)


def aggregate_stats(version):
    out_ver = os.path.join(OUT_DIR, f"org_{version}")
    total = 0
    seg_dist_all = Counter()
    type_dist_all = Counter()
    seq_dist_all = Counter()
    for i in range(NUM_CHUNKS):
        sp = os.path.join(out_ver, f"chunk_{i:02d}_stats.json")
        if os.path.exists(sp):
            with open(sp) as f:
                s = json.load(f)
            total += s["total"]
            seg_dist_all += Counter(s["seg_dist"])
            type_dist_all += Counter(s.get("type_dist", {}))
            seq_dist_all += Counter(s.get("seq_dist", {}))

    return {
        "version": version,
        "total": total,
        "seg_dist": dict(seg_dist_all.most_common()),
        "type_dist": dict(type_dist_all.most_common()),
        "seq_dist": dict(seq_dist_all.most_common()),
        "avg_segs": sum(int(k) * v for k, v in seg_dist_all.items()) / max(1, total),
    }


def compare_versions(all_stats):
    report = []
    report.append("# ORG 全量识别两版本对比报告 (训练语料)\n")
    report.append(f"> 数据源: data/split/org/ ({all_stats[0]['total']:,} 条)")
    report.append(f"> 词典版本: {all_stats[0]['version']} / {all_stats[1]['version']}\n")

    report.append("## 覆盖率\n")
    report.append("| 版本 | 总记录数 | 平均段数 | 段分布 (top 5) |")
    report.append("|------|:---:|:---:|------|")
    for s in all_stats:
        segs = ", ".join(f"{k}seg={v:,}" for k, v in sorted(s["seg_dist"].items(), key=lambda x: -int(x[1]))[:5])
        report.append(f"| {s['version']} | {s['total']:,} | {s['avg_segs']:.2f} | {segs} |")

    report.append("\n## 段类型分布 (全量)\n")
    report.append("| 类型 | v1.1.3 | v1.2.0 | 差异 |")
    report.append("|------|:---:|:---:|:---:|")
    all_types = set()
    for s in all_stats:
        all_types.update(s["type_dist"].keys())
    for t in sorted(all_types):
        a = all_stats[0]["type_dist"].get(t, 0)
        b = all_stats[1]["type_dist"].get(t, 0)
        diff = b - a
        report.append(f"| {t} | {a:,} | {b:,} | {diff:+,} |")

    report.append("\n## 段数分布\n")
    report.append("| 版本 | 1段 | 2段 | 3段 | 4段 | 5+段 |")
    report.append("|------|:---:|:---:|:---:|:---:|:---:|")
    for s in all_stats:
        sd = {int(k): v for k, v in s["seg_dist"].items()}
        total = s["total"]
        rows = []
        for n in range(1, 6):
            cnt = sum(v for k, v in sd.items() if k == n or (n == 5 and k >= 5))
            rows.append(f"{100*cnt/total:.1f}%")
        report.append(f"| {s['version']} | {' | '.join(rows)} |")

    report.append("\n## 识别差异对比 (chunk_00 全量, 按段文本边界)\n")

    version_pairs = [(all_stats[i]["version"], all_stats[i + 1]["version"]) for i in range(len(all_stats) - 1)]

    for ver_a, ver_b in version_pairs:
        path_a = os.path.join(OUT_DIR, f"org_{ver_a}", "chunk_00.jsonl")
        path_b = os.path.join(OUT_DIR, f"org_{ver_b}", "chunk_00.jsonl")
        diff_count = 0
        total = 0
        examples = []

        with open(path_a, encoding="utf-8") as fa, open(path_b, encoding="utf-8") as fb:
            for line_a, line_b in zip(fa, fb):
                total += 1
                ra = json.loads(line_a)
                rb = json.loads(line_b)
                seq_a = tuple(s["text"] for s in ra["segments"])
                seq_b = tuple(s["text"] for s in rb["segments"])
                if seq_a != seq_b:
                    diff_count += 1
                    if len(examples) < 5:
                        examples.append((ra["original"], seq_a, seq_b))

        pct = 100 * diff_count / max(1, total)
        report.append(f"\n### {ver_a} vs {ver_b}")
        report.append(f"- 总记录: {total:,}")
        report.append(f"- 段文本不一致: {diff_count:,} ({pct:.2f}%)")

        if examples:
            report.append(f"\n**不一致样例**:\n")
            for text, seq_a, seq_b in examples:
                report.append(f"- 「{text}」")
                report.append(f"  - {ver_a}: {' '.join(f'[{t}]' for t in seq_a)}")
                report.append(f"  - {ver_b}: {' '.join(f'[{t}]' for t in seq_b)}")

    report.append(f"\n## 汇总\n")
    report.append(f"| 版本对 | 不一致数 | 占比 |")
    report.append(f"|------|:---:|:---:|")
    # Rerun diff counts for summary
    for ver_a, ver_b in version_pairs:
        path_a = os.path.join(OUT_DIR, f"org_{ver_a}", "chunk_00.jsonl")
        path_b = os.path.join(OUT_DIR, f"org_{ver_b}", "chunk_00.jsonl")
        dc = 0
        with open(path_a, encoding="utf-8") as fa, open(path_b, encoding="utf-8") as fb:
            for line_a, line_b in zip(fa, fb):
                ra = json.loads(line_a)
                rb = json.loads(line_b)
                if tuple(s["text"] for s in ra["segments"]) != tuple(s["text"] for s in rb["segments"]):
                    dc += 1
        total = 0
        with open(path_a, encoding="utf-8") as f:
            for _ in f:
                total += 1
        report.append(f"| {ver_a}→{ver_b} | {dc:,} | {100*dc/max(1,total):.2f}% |")

    report.append(f"\n## 段类型序列分布\n")

    for n in range(1, 7):
        all_versions_seqs = []
        for s in all_stats:
            all_versions_seqs.append({k: v for k, v in s["seq_dist"].items() if k.count(" → ") + 1 == n})

        all_keys = set()
        for seqs in all_versions_seqs:
            all_keys.update(seqs.keys())
        key_totals = [(k, sum(seqs.get(k, 0) for seqs in all_versions_seqs)) for k in all_keys]
        filtered = [(k, t) for k, t in key_totals if t >= 50]
        filtered.sort(key=lambda x: -x[1])

        if not filtered:
            continue

        vnames = [s["version"] for s in all_stats]
        header = "| 序列 | " + " | ".join(vnames) + " |"
        sep = "|------|" + "|".join(["------:" for _ in vnames]) + "|"
        report.append(f"\n### {n}段序列 (top {min(15, len(filtered))})\n")
        report.append(header)
        report.append(sep)

        for seq, _ in filtered[:15]:
            vals = [f"{seqs.get(seq, 0):,}" for seqs in all_versions_seqs]
            report.append(f"| {seq} | " + " | ".join(vals) + " |")

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    report.append(f"\n> 报告生成: {now}")

    return "\n".join(report)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"

    if cmd in ("run", "all"):
        for ver in VERSIONS:
            print(f"\n{'='*50}", flush=True)
            print(f"Processing {ver}...", flush=True)
            run_version(ver)

    if cmd in ("compare", "all"):
        all_stats = [aggregate_stats(ver) for ver in VERSIONS]
        for s in all_stats:
            print(f"\n{json.dumps(s, ensure_ascii=False, indent=2)}", flush=True)
        report = compare_versions(all_stats)
        rpath = os.path.join(OUT_DIR, "org_eval_report.md")
        with open(rpath, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\nSaved: {rpath}", flush=True)


if __name__ == "__main__":
    main()
