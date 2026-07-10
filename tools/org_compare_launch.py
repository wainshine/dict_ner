#!/usr/bin/env python3
"""三版本 ORG 全量识别 → 对比评估"""
import os, sys, time, json, subprocess
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "data")
OUT_DIR = os.path.join(BASE, "output", "org_compare")
WORKER = os.path.join(BASE, "tools", "org_process_worker.py")

COMPANY_INPUT = os.path.join(DATA_DIR, "公司名input.txt")
COMPANY_SPLIT = os.path.join(DATA_DIR, "split", "org_company")
NUM_CHUNKS = 16
VERSIONS = ["v1.1.1", "v1.1.2", "v1.1.3", "v1.2.0"]

os.makedirs(OUT_DIR, exist_ok=True)


def split_input():
    """Split 公司名input.txt (GBK) into 16 UTF-8 chunks."""
    os.makedirs(COMPANY_SPLIT, exist_ok=True)
    # Check if already split
    if os.path.exists(os.path.join(COMPANY_SPLIT, "chunk_00.csv")):
        print(f"Chunks exist at {COMPANY_SPLIT}, skipping split", flush=True)
        return

    from tools.pipeline_base import count_lines
    total = count_lines(COMPANY_INPUT)
    per = (total + NUM_CHUNKS - 1) // NUM_CHUNKS
    print(f"Split 公司名input.txt: {total:,} lines → {NUM_CHUNKS} chunks x ~{per:,}", flush=True)

    writers = [open(os.path.join(COMPANY_SPLIT, f"chunk_{i:02d}.csv"), "w", encoding="utf-8")
               for i in range(NUM_CHUNKS)]
    with open(COMPANY_INPUT, encoding="gbk", errors="replace") as f:
        for i, line in enumerate(f):
            text = line.strip()
            if not text:
                continue
            chunk_id = i * NUM_CHUNKS // total if total > 0 else 0
            writers[chunk_id].write(text + "\n")
            if (i + 1) % 5000000 == 0:
                print(f"  {i // 10000:>4}w written", flush=True)
    for w in writers:
        w.close()
    print("  Split done", flush=True)


def run_version(version):
    """Run 16 parallel workers for one dict version."""
    out_ver = os.path.join(OUT_DIR, f"org_{version}")
    os.makedirs(out_ver, exist_ok=True)

    first_jsonl = os.path.join(out_ver, "chunk_00.jsonl")
    if os.path.exists(first_jsonl):
        print(f"  {version}: already done, skipping", flush=True)
        return

    t0 = time.time()
    procs = []
    for i in range(NUM_CHUNKS):
        chunk = os.path.join(COMPANY_SPLIT, f"chunk_{i:02d}.csv")
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
        out_text = p.communicate(timeout=3600)[0]
        if out_text:
            for line in out_text.strip().split("\n")[-2:]:
                print(f"  [{version} chunk_{i:02d}] {line}", flush=True)
    elapsed = time.time() - t0
    print(f"  {version}: {len(procs)} chunks done in {elapsed:.0f}s ({elapsed/60:.1f}min)", flush=True)


def aggregate_stats(version):
    """Aggregate per-chunk stats for one version."""
    out_ver = os.path.join(OUT_DIR, f"org_{version}")
    total = 0
    seg_dist_all = Counter()
    for i in range(NUM_CHUNKS):
        sp = os.path.join(out_ver, f"chunk_{i:02d}_stats.json")
        if os.path.exists(sp):
            with open(sp) as f:
                s = json.load(f)
            total += s["total"]
            seg_dist_all += Counter(s["seg_dist"])

    return {
        "version": version,
        "total": total,
        "seg_dist": dict(seg_dist_all.most_common()),
        "avg_segs": sum(int(k) * v for k, v in seg_dist_all.items()) / max(1, total),
    }


def compare_versions(all_stats):
    """Generate comparison report from per-version stats."""
    report = []
    report.append("# ORG 全量识别四版本对比报告\n")
    report.append(f"> 数据源: 公司名input.txt ({all_stats[0]['total']:,} 条)")
    report.append(f"> 词典版本: v1.1.1 / v1.1.2 / v1.1.3 / v1.2.0\n")

    report.append("## 覆盖率\n")
    report.append("| 版本 | 总记录数 | 平均段数 | 段分布 (top 5) |")
    report.append("|------|:---:|:---:|------|")
    for s in all_stats:
        segs = ", ".join(f"{k}seg={v:,}" for k, v in sorted(s["seg_dist"].items(), key=lambda x: -int(x[1]))[:5])
        report.append(f"| {s['version']} | {s['total']:,} | {s['avg_segs']:.2f} | {segs} |")

    report.append("\n## 段类型分布\n")
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
    total_checked = 0
    all_diffs = {}

    version_pairs = [
        ("v1.1.1 vs v1.1.2", "v1.1.1", "v1.1.2"),
        ("v1.1.2 vs v1.1.3", "v1.1.2", "v1.1.3"),
        ("v1.1.3 vs v1.2.0", "v1.1.3", "v1.2.0"),
    ]

    for ver_pair, ver_a, ver_b in version_pairs:
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
                    if len(examples) < 10:
                        examples.append((ra["original"], seq_a, seq_b))

        pct = 100 * diff_count / max(1, total)
        report.append(f"\n### {ver_pair}")
        report.append(f"- 总记录: {total:,}")
        report.append(f"- 段文本不一致: {diff_count:,} ({pct:.2f}%)")

        all_diffs[ver_pair] = diff_count
        total_checked = total

        if examples:
            report.append(f"\n**不一致样例**:\n")
            for text, seq_a, seq_b in examples[:5]:
                report.append(f"- 「{text}」")
                report.append(f"  - {ver_a}: {' '.join(f'[{t}]' for t in seq_a)}")
                report.append(f"  - {ver_b}: {' '.join(f'[{t}]' for t in seq_b)}")

    report.append(f"\n## 汇总\n")
    report.append(f"| 版本对 | 不一致数 | 占比 | 增量 |")
    report.append(f"|------|:---:|:---:|:---:|")
    prev = 0
    for ver_pair, _, _ in version_pairs:
        cnt = all_diffs.get(ver_pair, 0)
        pct = 100 * cnt / max(1, total_checked)
        delta = cnt - prev
        report.append(f"| {ver_pair} | {cnt:,} | {pct:.2f}% | Δ{delta:+,} |")
        prev = cnt

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    report.append(f"\n> 报告生成: {now}")

    return "\n".join(report)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"

    if cmd in ("split", "all"):
        split_input()

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
        rpath = os.path.join(OUT_DIR, "org_compare_report.md")
        with open(rpath, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\nSaved: {rpath}", flush=True)


if __name__ == "__main__":
    main()
