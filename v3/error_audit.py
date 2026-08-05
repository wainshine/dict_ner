#!/usr/bin/env python3
"""test 集错误逐类诊断 — 四大迁移类聚类 + 样例 (P2 诊断, 只产出不改模型)

产出: output/v4_f1_error_audit.md
用法: python3 v3/error_audit.py [--n 0(全量)]
"""
import argparse
import csv
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEATS = os.path.join(BASE, "output", "v3_feat", "test_feats.csv")
OUT_MD = os.path.join(BASE, "output", "v4_f1_error_audit.md")
TOP_PAIRS = [("ORG", "POI"), ("POI", "ORG"), ("POI", "ADDR"), ("ADDR", "POI"),
             ("ORG", "ADDR"), ("ADDR", "ORG")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=0)
    args = ap.parse_args()

    from v3.poi_recall_audit import cluster_of
    from v3.infer import V3Classifier
    clf = V3Classifier()

    rows = []
    with open(FEATS, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append((r["text"], r["label"], r.get("source", "")))
            if args.n and len(rows) >= args.n:
                break
    preds = clf.classify_batch([t for t, _, _ in rows])

    errors = defaultdict(list)  # (exp, pred) -> [(text, conf, source)]
    n_correct = 0
    for (text, label, source), p in zip(rows, preds):
        if p["category"] == label:
            n_correct += 1
        else:
            errors[(label, p["category"])].append((text, p["confidence"], source))

    lines = ["# test 集错误逐类诊断 (v4.0.2 模型)", "",
             f"总样本 {len(rows):,}, 正确 {n_correct:,} "
             f"(accuracy {n_correct/len(rows):.4f})", ""]
    for pair in sorted(errors, key=lambda k: -len(errors[k])):
        items = errors[pair]
        if pair not in TOP_PAIRS and len(items) < 100:
            continue
        exp, pred = pair
        lines += [f"## {exp} → {pred} ({len(items)} 条)", "",
                  "| 簇 | 数量 | 占比 | 平均置信度 |",
                  "|----|-----:|-----:|-----------:|"]
        clusters = defaultdict(list)
        for text, conf, source in items:
            clusters[cluster_of(text)].append((text, conf, source))
        for cname, members in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
            avg = sum(c for _, c, _ in members) / len(members)
            lines.append(f"| {cname} | {len(members)} | "
                         f"{100*len(members)/len(items):.1f}% | {avg:.3f} |")
        lines.append("")
        for cname, members in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
            members.sort(key=lambda x: -x[1])
            samples = "、".join(f"`{t}`({s})" for t, _, s in members[:6])
            lines.append(f"- **{cname}** ({len(members)}): {samples}")
        lines.append("")

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"written: {OUT_MD}")
    for pair in sorted(errors, key=lambda k: -len(errors[k])):
        print(f"{pair[0]} → {pair[1]}: {len(errors[pair])}")


if __name__ == "__main__":
    main()
