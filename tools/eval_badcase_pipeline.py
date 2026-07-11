#!/usr/bin/env python3
"""Pipeline-level badcase 评估 — 用 pipe.classify() 替代裸识别器，测试复合检测/过度拆分合并效果"""
import argparse, csv, json, os, sys, pickle, time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_seq_freqs_jsonl(eval_name, version):
    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "output", f"{eval_name}_eval", f"{eval_name}_{version}")
    if not os.path.isdir(base_dir):
        return Counter()

    all_seqs = Counter()
    for fname in sorted(os.listdir(base_dir)):
        if not fname.endswith(".jsonl"):
            continue
        spath = os.path.join(base_dir, fname.replace(".jsonl", "_stats.json"))
        if os.path.exists(spath):
            with open(spath, "r", encoding="utf-8", errors="replace") as f:
                s = json.load(f)
            all_seqs += Counter(s.get("seq_dist", {}))
    return all_seqs


def get_org_seq_via_pipeline(text, pipe):
    r = pipe.classify(text)
    org_segs = r.get("all", {}).get("org", {}).get("segments", [])
    if not org_segs and r.get("best"):
        org_segs = r.get("best", {}).get("segments", [])
    return " → ".join(s["type"] for s in org_segs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--badcase", required=True)
    parser.add_argument("--versions", required=True)
    parser.add_argument("--eval", required=True, choices=["org", "poi", "loc"])
    args = parser.parse_args()

    versions = args.versions.split(",")

    with open(args.badcase, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    texts = [r["text"] for r in rows]
    old_seqs = [r["seq"] for r in rows]

    version_seqs = {}
    version_freqs = {}
    for v in versions:
        print(f"Pipeline classifying with {v}...", flush=True)
        from pipeline import DictNerPipeline
        pipe = DictNerPipeline(org_dict=v, poi_dict=v, loc_dict=f"loc_{v}")
        seqs = []
        for text in texts:
            seqs.append(get_org_seq_via_pipeline(text, pipe))
        version_seqs[v] = seqs
        version_freqs[v] = load_seq_freqs_jsonl(args.eval, v)
        print(f"  done: {len(seqs)} items", flush=True)

    results_by_pair = defaultdict(lambda: {"REPAIRED": 0, "STILL_LOW": 0, "CHANGED": 0})

    for i in range(len(versions) - 1):
        va, vb = versions[i], versions[i + 1]
        freqs_a = version_freqs[va]
        freqs_b = version_freqs[vb]

        for j in range(len(texts)):
            old_seq = old_seqs[j]
            new_seq = version_seqs[vb][j]
            old_freq = freqs_a.get(old_seq, 0)
            new_freq = freqs_b.get(new_seq, 0)

            if new_freq >= 10:
                results_by_pair[(va, vb)]["REPAIRED"] += 1
            elif new_seq != old_seq:
                results_by_pair[(va, vb)]["CHANGED"] += 1
            else:
                results_by_pair[(va, vb)]["STILL_LOW"] += 1

    report_lines = ["# Pipeline Badcase 跨版本评估\n"]
    report_lines.append(f"> 数据源: {os.path.basename(args.badcase)}")
    report_lines.append(f"> 方法: pipe.classify() (含复合检测+过度拆分合并)\n")
    report_lines.append("| 版本对 | 总 badcase | REPAIRED | STILL_LOW | CHANGED | 修复率 |")
    report_lines.append("|------|-----:|-----:|-----:|-----:|-----:|")

    for (va, vb), counts in results_by_pair.items():
        total = sum(counts.values())
        repaired = counts["REPAIRED"]
        report_lines.append(f"| {va}→{vb} | {total:,} | {repaired:,} | "
                           f"{counts['STILL_LOW']:,} | {counts['CHANGED']:,} | "
                           f"{100*repaired/max(1,total):.1f}% |")

    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "output", "badcase_pipeline_report.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print("\n".join(report_lines))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
