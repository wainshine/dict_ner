#!/usr/bin/env python3
"""Badcase 跨版本评估 → 修复率报告"""
import argparse, csv, json, os, sys, time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def load_seq_freqs(eval_name, version):
    import pickle
    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "output", f"{eval_name}_eval", f"{eval_name}_{version}")
    all_seqs = Counter()
    for fname in sorted(os.listdir(base_dir)):
        if not fname.endswith(".jsonl"):
            continue
        spath = os.path.join(base_dir, fname.replace(".jsonl", "_stats.json"))
        if os.path.exists(spath):
            with open(spath, "r", encoding="utf-8", errors="replace") as f:
                s = json.load(f)
            all_seqs += Counter(s.get("seq_dist", {}))
        else:
            spath = os.path.join(base_dir, fname.replace(".jsonl", "_stats.pkl"))
            if os.path.exists(spath):
                with open(spath, "rb") as f:
                    s = pickle.load(f)
                all_seqs += Counter(s.get("seq_dist", {}))
    return all_seqs


def get_seq_for_version(eval_name, version, texts):
    if eval_name == "org":
        from v2.org_recognizer import OrgDPRecognizer
        rec = OrgDPRecognizer(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "data"), version=version)
    elif eval_name == "poi":
        from v2.poi_recognizer import PoiRecognizer
        rec = PoiRecognizer(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "data"), dict_name=f"poi_{version}.pkl")
    else:
        from v2.loc_builder import DictBuilder
        from v2.loc_recognizer import AddressRecognizer
        b = DictBuilder.load(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "dicts"), f"loc_{version}")
        rec = AddressRecognizer(b.dict_data)

    results = []
    for text in texts:
        res = rec.recognize(text)
        seq = " → ".join(s.seg_type.value for s in res.segments)
        results.append(seq)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--badcase", required=True)
    parser.add_argument("--versions", required=True)
    parser.add_argument("--eval", required=True, choices=["org", "poi", "loc"])
    args = parser.parse_args()

    with open(args.badcase, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    texts = [r["text"] for r in rows]
    old_seqs = [r["seq"] for r in rows]
    versions = args.versions.split(",")

    version_seqs = {}
    version_freqs = {}
    for v in versions:
        print(f"Running {v}...", flush=True)
        version_seqs[v] = get_seq_for_version(args.eval, v, texts)
        version_freqs[v] = load_seq_freqs(args.eval, v)

    results_by_pair = defaultdict(lambda: {"REPAIRED": 0, "STILL_LOW": 0, "CHANGED_LOW": 0, "UNCHANGED": 0})
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
                results_by_pair[(va, vb)]["CHANGED_LOW"] += 1
            elif new_freq < 10:
                results_by_pair[(va, vb)]["STILL_LOW"] += 1
            else:
                results_by_pair[(va, vb)]["STILL_LOW"] += 1

    report_lines = ["# Badcase 跨版本评估\n"]
    report_lines.append(f"| 版本对 | 总 badcase | REPAIRED | STILL_LOW | CHANGED | 修复率 |")
    report_lines.append("|------|-----:|-----:|-----:|-----:|-----:|")
    for (va, vb), counts in results_by_pair.items():
        total = sum(counts.values())
        repaired = counts["REPAIRED"]
        report_lines.append(f"| {va}→{vb} | {total:,} | {repaired:,} | "
                           f"{counts['STILL_LOW']:,} | {counts['CHANGED_LOW']:,} | "
                           f"{100*repaired/max(1,total):.1f}% |")

    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "output", "badcase_eval_report.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print("\n".join(report_lines))
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
