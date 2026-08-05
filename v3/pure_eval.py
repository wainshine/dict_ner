#!/usr/bin/env python3
"""纯净集评测 launcher — org_company(ORG纯净) + split/poi(POI纯净)

用法:
  python v3/pure_eval.py run <org_pure|poi_pure> [total_n]
  python v3/pure_eval.py report
"""
import glob
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
OUT_DIR = os.path.join(BASE, "output", "v3_pure_eval")
LABELS = ("ORG", "POI", "ADDR", "UNKNOWN")


def run(system, total_n=1000000):
    os.makedirs(OUT_DIR, exist_ok=True)
    if system == "org_pure":
        chunks = sorted(glob.glob(os.path.join(DATA, "split", "org_company", "chunk_*.csv")))
    else:
        chunks = sorted(glob.glob(os.path.join(DATA, "split", "poi", "chunk_*.csv")))
    per = max(1000, total_n // len(chunks))
    worker = os.path.join(BASE, "v3", "pure_eval_worker.py")
    procs = []
    for c in chunks:
        name = os.path.basename(c).replace(".csv", "")
        out = os.path.join(OUT_DIR, f"{system}_{name}.json")
        log = os.path.join(OUT_DIR, f"{system}_{name}.log")
        with open(log, "w") as lf:
            p = subprocess.Popen([sys.executable, worker, system, c, str(per), out],
                                 stdout=lf, stderr=subprocess.STDOUT)
        procs.append((name, p))
    print(f"[{system}] launched {len(procs)} workers, {per:,}/chunk")
    failed = [n for n, p in procs if p.wait() != 0]
    print(f"[{system}] done, failed: {failed or 'none'}", flush=True)
    return not failed


def report():
    from v3.poi_recall_audit import (
        cluster_of, split_verdict, other_boundary_likely)
    lines = ["# 纯净集评测报告", ""]
    for system, desc in (("org_pure", "ORG 纯净集 (org_company 公司名语料)"),
                         ("poi_pure", "POI 纯净集 (split/poi POI语料)")):
        files = sorted(glob.glob(os.path.join(OUT_DIR, f"{system}_*.json")))
        if not files:
            continue
        total = {lb: 0 for lb in LABELS}
        conf_sum = {lb: 0.0 for lb in LABELS}
        conf_n = {lb: 0 for lb in LABELS}
        sampled = corpus = 0
        wrong = []
        for fp in files:
            r = json.load(open(fp, encoding="utf-8"))
            for lb in LABELS:
                total[lb] += r["counts"][lb]
                cnt = r["counts"][lb]
                conf_sum[lb] += r["avg_conf"][lb] * cnt
                conf_n[lb] += cnt
            sampled += r["sampled"]
            corpus += r["corpus_total"]
            wrong.extend(r["wrong_examples"])
        n = sum(total.values())
        expected = "ORG" if system == "org_pure" else "POI"
        lines += [f"## {desc} (语料 {corpus:,}, 抽样 {sampled:,})", "",
                  "| 判定 | 数量 | 占比 | 平均置信度 |",
                  "|------|-----:|-----:|-----------:|"]
        for lb in LABELS:
            mark = " ✓" if lb == expected else ""
            ac = conf_sum[lb] / max(1, conf_n[lb])
            lines.append(f"| {lb}{mark} | {total[lb]:,} | {100*total[lb]/n:.2f}% | {ac:.3f} |")
        recall = total[expected] / n
        lines += ["", f"**纯净召回率: {100*recall:.2f}%**", ""]

        # 分层口径: 真边界剔除后的有效召回 (v4.0.1+, 判定规则见 v3/poi_recall_audit.py)
        verdict_n = {"boundary": 0, "error": 0, "noise": 0}
        other_boundary = other_total = 0
        for name, cat, _conf in wrong:
            if system == "org_pure":
                # D0 审查: 门店形态→POI / 内嵌地址→ADDR 均为体系边界, UNKNOWN 为噪声
                v = "noise" if cat == "UNKNOWN" else "boundary"
            else:
                v = split_verdict(cat, cluster_of(name))
                if v == "error" and cat == "ADDR" and cluster_of(name) == "其他":
                    other_total += 1
                    if other_boundary_likely(name):
                        other_boundary += 1
            verdict_n[v] += 1
        n_wrong = sum(verdict_n.values())
        if n_wrong:
            wrong_total = n - total[expected]
            err_ratio = verdict_n["error"] / n_wrong
            eff = total[expected] / (total[expected] + wrong_total * err_ratio)
            line = (f"**有效召回 (真边界剔除): {100*eff:.1f}%**"
                    if verdict_n["error"] else "")
            lines += [f"### 分层口径 (误判样本 {n_wrong} 条: "
                      f"boundary {verdict_n['boundary']} / "
                      f"error {verdict_n['error']} / noise {verdict_n['noise']})", ""]
            if verdict_n["error"]:
                err_opt = (verdict_n["error"] - other_boundary) / n_wrong
                eff_opt = total[expected] / (total[expected] + wrong_total * err_opt)
                lines.append(f"- 有效召回 = {expected} / ({expected} + 真错误估计): "
                             f"**悲观 {100*eff:.1f}% ~ 乐观 {100*eff_opt:.1f}%**")
                lines.append("")
            else:
                lines += [f"- 误判全部为体系边界/噪声, **有效召回 ≈ 100%**", ""]
        lines += ["### 误判样例 (按置信度排序 top30)", ""]
        wrong.sort(key=lambda x: -x[2])
        for name, cat, conf in wrong[:30]:
            lines.append(f"- `{name}` → {cat} (conf={conf})")
        lines.append("")
    path = os.path.join(OUT_DIR, "..", "v3_pure_eval_report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines[:50]))
    print(f"\nreport: {path}")


def main():
    cmd = sys.argv[1]
    if cmd == "run":
        total_n = int(sys.argv[3]) if len(sys.argv) > 3 else 1000000
        ok = run(sys.argv[2], total_n)
        sys.exit(0 if ok else 1)
    elif cmd == "report":
        report()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
