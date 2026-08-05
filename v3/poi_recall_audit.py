#!/usr/bin/env python3
"""POI 纯净召回诊断 — 误判样例按后缀模式聚类 (D0 诊断, 只产出不改代码)

数据源: output/v3_pure_eval/poi_pure_*.json 的 wrong_examples (16 chunk × 200)
产出:   output/v4_poi_recall_audit.md

用法: python3 v3/poi_recall_audit.py
"""
import glob
import json
import os
import re
import sys
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN_GLOB = os.path.join(BASE, "output", "v3_pure_eval", "poi_pure_*.json")
OUT_MD = os.path.join(BASE, "output", "v4_poi_recall_audit.md")

CLUSTER_RULES = [
    ("交叉口", lambda n: "交叉口" in n),
    ("门牌号结尾", lambda n: bool(re.search(r"[0-9０-９]+号$", n))),
    ("纯路街巷名", lambda n: n.endswith(("路", "街", "巷", "大道", "大街", "公路", "胡同", "弄", "道"))),
    ("村/社区/庄", lambda n: n.endswith(("村", "社区", "屯", "庄", "寨"))),
    ("小区/家园/花园", lambda n: any(k in n for k in ("家园", "小区", "花园", "花苑", "公寓", "苑"))),
    ("公园/景区/寺山", lambda n: any(k in n for k in ("公园", "景区", "风景", "寺", "庙", "湿地", "森林", "陵")) or n.endswith(("山", "湖"))),
    ("酒店/宾馆/大厦", lambda n: any(k in n for k in ("酒店", "宾馆", "大厦", "饭店", "旅馆", "客栈"))),
    ("商超/广场", lambda n: any(k in n for k in ("超市", "商场", "广场", "百货", "市场", "商店"))),
    ("自然地名", lambda n: n.endswith((
        "沟", "峪", "湾", "岔", "坡", "梁", "坪", "岗", "咀", "嘴", "凹", "洼",
        "塘", "坨", "甸", "坝", "岭", "峰", "岩", "洞", "滩", "洲", "岛", "江",
        "河", "溪", "泉", "井", "池", "库", "桥"))),
    ("政府机构", lambda n: any(k in n for k in (
        "人民政府", "派出所", "村委会", "居委会", "委员会", "公安", "法院",
        "检察院", "税务", "工商", "财政", "司法", "大队", "办事处", "政务"))),
    ("医院/学校", lambda n: any(k in n for k in (
        "医院", "卫生院", "卫生室", "卫生所", "学校", "中学", "小学", "幼儿园", "学院", "大学", "驾校"))),
    ("银行/网点", lambda n: any(k in n for k in ("支行", "分行", "信用社", "银行", "联社", "营业部"))),
    ("公司/厂", lambda n: any(k in n for k in ("有限公司", "公司", "集团", "厂"))),
    ("局/所/中心", lambda n: any(k in n for k in ("局", "所", "中心"))),
    ("含数字/字母", lambda n: bool(re.search(r"[0-9a-zA-Z]", n))),
]

# D0 人工审查判定 (v4_poi_recall_audit.md):
# - ORG 桶: 全簇真边界 (机关/医院/学校/厂公司 = v2.1 体系 ORG, 地图源标 POI 点位)
# - ADDR 桶: 边界簇 vs 真错误簇 (高置信误判, 见机制抽查)
_ADDR_BOUNDARY_CLUSTERS = {
    "交叉口", "纯路街巷名", "村/社区/庄", "门牌号结尾",
    "小区/家园/花园", "自然地名", "含数字/字母",   # 楼栋号/门牌点位
    "政府机构", "医院/学校", "公司/厂", "银行/网点",  # 宿舍/家属院/综合楼类
}


def split_verdict(cat: str, cluster: str) -> str:
    """误判样例分诊: boundary(体系边界, 不计错误) / error(真错误) / noise"""
    if cat == "UNKNOWN":
        return "noise"
    if cat == "ORG":
        return "boundary"
    if cat == "ADDR":
        return "boundary" if cluster in _ADDR_BOUNDARY_CLUSTERS else "error"
    return "error"


# "其他" 簇二次细分 (人工抽查: 约半数为楼盘/自然地名/街段, 属边界)
_OTHER_BOUNDARY_LIKELY = re.compile(
    r"(园|庭|苑|城|楼|轩|府|墅|豪庭|花都|香庭|半岛|国际|新城|居住区|住宅区"
    r"|乡$|镇$|区$|街.{0,2}段$|新村$|新区$|开发区$)")


def other_boundary_likely(name: str) -> bool:
    return bool(_OTHER_BOUNDARY_LIKELY.search(name))


def cluster_of(name):
    for cname, rule in CLUSTER_RULES:
        if rule(name):
            return cname
    return "其他"


def main():
    files = sorted(glob.glob(IN_GLOB))
    if not files:
        print(f"no input: {IN_GLOB}")
        sys.exit(1)

    buckets = defaultdict(list)  # pred_label -> [(name, conf)]
    counts = defaultdict(int)    # pred_label -> 全量计数
    sampled_total = 0
    for fp in files:
        r = json.load(open(fp, encoding="utf-8"))
        for name, cat, conf in r["wrong_examples"]:
            buckets[cat].append((name, conf))
        for lb, c in r["counts"].items():
            counts[lb] += c
        sampled_total += r["sampled"]

    lines = ["# POI 纯净召回 D0 诊断报告", "",
             f"数据源: {len(files)} 个 poi_pure chunk 的 wrong_examples "
             f"(每 chunk 前 200 条误判, 名称经蓄水池抽样)", ""]
    verdict_n = defaultdict(int)
    for cat in ("ORG", "ADDR", "UNKNOWN"):
        items = buckets.get(cat, [])
        if not items:
            continue
        lines += [f"## POI → {cat} ({len(items)} 条)", "",
                  "| 簇 | 数量 | 占比 | 平均置信度 | 判定 |",
                  "|----|-----:|-----:|-----------:|------|"]
        clusters = defaultdict(list)
        for name, conf in items:
            clusters[cluster_of(name)].append((name, conf))
        ordered = sorted(clusters.items(), key=lambda kv: -len(kv[1]))
        for cname, members in ordered:
            avg = sum(c for _, c in members) / len(members)
            verdict = split_verdict(cat, cname)
            verdict_n[verdict] += len(members)
            lines.append(f"| {cname} | {len(members)} | "
                         f"{100*len(members)/len(items):.1f}% | {avg:.3f} | {verdict} |")
        lines.append("")
        for cname, members in ordered:
            members.sort(key=lambda x: -x[1])
            samples = "、".join(f"`{n}`" for n, _ in members[:8])
            lines.append(f"- **{cname}** ({len(members)}): {samples}")
        lines.append("")

    # 有效召回外推 (wrong_examples 抽样比 ≈ 全量分布, ±~1.5%)
    n_wrong_samples = sum(verdict_n.values())
    if n_wrong_samples and counts.get("POI"):
        err_ratio = verdict_n["error"] / n_wrong_samples
        wrong_total = sum(c for lb, c in counts.items() if lb != "POI")
        err_est = wrong_total * err_ratio
        eff = counts["POI"] / (counts["POI"] + err_est)
        raw = counts["POI"] / sum(counts.values())
        # 乐观口径: "其他" 簇中楼盘/自然地名/街段类按边界剔除
        other_items = [n for n, _ in buckets.get("ADDR", [])
                       if cluster_of(n) == "其他"]
        other_boundary = sum(1 for n in other_items if other_boundary_likely(n))
        err_ratio_opt = (verdict_n["error"] - other_boundary) / n_wrong_samples
        eff_opt = counts["POI"] / (counts["POI"] + wrong_total * err_ratio_opt)
        lines += ["## 有效召回 (分层口径)", "",
                  f"- 抽样误判 {n_wrong_samples} 条: boundary {verdict_n['boundary']} "
                  f"/ error {verdict_n['error']} / noise {verdict_n['noise']}",
                  f"- 全量计数: {dict(counts)}",
                  f"- 原始纯净召回: **{100*raw:.2f}%**",
                  f"- 真错误占比(误判样本外推): {100*err_ratio:.1f}% "
                  f"(其中\"其他\"簇 {len(other_items)} 条, 人工启发式细分后 "
                  f"楼盘/地名类 {other_boundary} 条更像边界)",
                  f"- **有效召回 = POI / (POI + 真错误估计): "
                  f"悲观 {100*eff:.1f}% ~ 乐观 {100*eff_opt:.1f}%**",
                  ""]

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"written: {OUT_MD}")
    for cat in ("ORG", "ADDR", "UNKNOWN"):
        print(f"POI → {cat}: {len(buckets.get(cat, []))}")


if __name__ == "__main__":
    main()
