#!/usr/bin/env python3
"""三版本全维度对比 — 词典 + 样本 + 差异统计"""
import os, sys, time, random, pickle, csv
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_DIR = os.path.join(BASE, "dicts")
DATA_DIR = os.path.join(BASE, "data")
OUT_DIR = os.path.join(BASE, "output", "comparison")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(os.path.join(OUT_DIR, "dicts"), exist_ok=True)
os.makedirs(os.path.join(OUT_DIR, "samples"), exist_ok=True)

VERSIONS = ["v1.1.0", "v1.1.1", "v1.1.2"]

# ══════════════════════════════════════════════════════════════
# PART 1: 词典 Top-N 导出
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("PART 1: 词典 Top-50 高频词导出")
print("=" * 60)

for ver in VERSIONS:
    # Org dict
    org_path = os.path.join(DICT_DIR, f"org_{ver}.pkl")
    poi_path = os.path.join(DICT_DIR, f"poi_{ver}.pkl")
    brand_path = os.path.join(DICT_DIR, f"brand_{ver}.pkl")

    if os.path.exists(org_path):
        with open(org_path, "rb") as f:
            org = pickle.load(f)
        # d1 top 50
        d1_items = sorted(org["d1_freqs"].items(), key=lambda x: -x[1])[:50]
        lines = [f"{w:30s} {f:>10,}" for w, f in d1_items]
        with open(os.path.join(OUT_DIR, "dicts", f"org_d1_top50_{ver}.txt"), "w", encoding="utf-8") as f:
            f.write("word                           freq\n")
            f.write("-" * 50 + "\n")
            f.write("\n".join(lines))
        # d4 top 50
        d4_items = sorted(org["d4_freqs"].items(), key=lambda x: -x[1])[:50]
        lines = [f"{w:30s} {f:>10,}" for w, f in d4_items]
        with open(os.path.join(OUT_DIR, "dicts", f"org_d4_top50_{ver}.txt"), "w", encoding="utf-8") as f:
            f.write("word                           freq\n")
            f.write("-" * 50 + "\n")
            f.write("\n".join(lines))
        print(f"  org_{ver}: d1={len(org['d1_freqs']):,}, d3={len(org['d3_freqs']):,}, d4={len(org['d4_freqs']):,}")

    if os.path.exists(poi_path):
        with open(poi_path, "rb") as f:
            poi = pickle.load(f)
        d1_items = sorted(poi["d1_freqs"].items(), key=lambda x: -x[1])[:50]
        lines = [f"{w:30s} {f:>10,}" for w, f in d1_items]
        with open(os.path.join(OUT_DIR, "dicts", f"poi_d1_top50_{ver}.txt"), "w", encoding="utf-8") as f:
            f.write("word                           freq\n")
            f.write("-" * 50 + "\n")
            f.write("\n".join(lines))
        d4_items = sorted(poi["d4_freqs"].items(), key=lambda x: -x[1])[:50]
        lines = [f"{w:30s} {f:>10,}" for w, f in d4_items]
        with open(os.path.join(OUT_DIR, "dicts", f"poi_d4_top50_{ver}.txt"), "w", encoding="utf-8") as f:
            f.write("word                           freq\n")
            f.write("-" * 50 + "\n")
            f.write("\n".join(lines))
        print(f"  poi_{ver}: d1={len(poi['d1_freqs']):,}, d3={len(poi['d3_freqs']):,}, d4={len(poi['d4_freqs']):,}")

    if os.path.exists(brand_path):
        with open(brand_path, "rb") as f:
            brand = pickle.load(f)
        bigrams = sorted(brand["bigram_counts"].items(), key=lambda x: -x[1])[:50]
        lines = [f"{pair:20s} {cnt:>12,}" for pair, cnt in bigrams]
        with open(os.path.join(OUT_DIR, "dicts", f"brand_bigrams_top50_{ver}.txt"), "w", encoding="utf-8") as f:
            f.write("bigram                      count\n")
            f.write("-" * 45 + "\n")
            f.write("\n".join(lines))
        print(f"  brand_{ver}: bigrams={len(brand['bigram_counts']):,}, total={brand['total_bigrams']:,}")

print()

# ══════════════════════════════════════════════════════════════
# PART 2: 三维度 × 三版本 识别样本对比
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("PART 2: 识别样本对比 (30条精选)")
print("=" * 60)

from pipeline import DictNerPipeline

SAMPLES = [
    # 标准地址 + 机构
    ("深圳市南山区华为技术有限公司", "标准地址+公司"),
    ("北京市朝阳区星巴克咖啡国贸店", "地址+品牌+POI"),
    ("陕西省安康市旬阳县XX公司", "四级地址+公司"),
    ("浙江省杭州市西湖区文三路478号华星时代广场", "五级地址+门牌"),
    # 复杂机构
    ("中国工商银行股份有限公司北京分行", "多后缀机构"),
    ("阿里巴巴网络技术有限公司", "知名品牌机构"),
    ("峨眉山景区游客中心", "景区+POI"),
    ("上海市浦东新区陆家嘴环路1000号恒生银行大厦", "地址+品牌+大厦"),
    ("广州市天河区体育西路191号中石化大厦", "地址+路名+大厦"),
    # POI + 边界歧义
    ("深圳福田区华强北路赛格广场", "区-路-广场"),
    ("北京市朝阳区建外SOHO东区A座", "英文+区+座"),
    ("上海南京东路步行街", "短地址+街"),
    ("广州市天河区岗顶", "区+地名"),
    ("成都高新区天府软件园D区", "高新区+园区"),
    # 歧义场景
    ("北京市东城区西门", "方位词POI歧义"),
    ("深圳市南山区路东", "路+方位歧义"),
    ("南京鼓楼区医院", "区+医院"),
    ("长沙市岳麓区大学城", "区+学城"),
    # 品牌名测试
    ("字节跳动科技有限公司", "互联网公司"),
    ("华为技术有限公司", "短品牌公司"),
    ("北京市海淀区中关村软件园", "中关村"),
    ("深圳市南山区大冲商务中心", "综合体"),
    ("西安钟楼饭店", "短地址+饭店"),
    ("厦门市思明区曾厝垵", "旅游地名"),
    # 边缘场景
    ("中国石油天然气集团公司", "长公司名"),
    ("北京市朝阳区三里屯太古里", "商业区"),
    ("黄山市黄山风景区", "景区"),
    ("拉萨市城关区布达拉宫广场", "长地名+景点"),
    ("北京市朝阳区望京SOHO", "短地址+英文"),
    ("深圳市宝安区西乡街道桃源居", "街道+小区"),
]

PIPES = {}
for ver in VERSIONS:
    PIPES[ver] = DictNerPipeline(
        loc_dict=f"loc_{ver}",
        org_dict=ver,
        poi_dict=f"poi_{ver}",
    )
    print(f"  Loaded pipeline {ver}")

report_lines = []
report_lines.append("# 三版本识别对比报告\n")
report_lines.append(f"## 样本识别 ({len(SAMPLES)}条)\n")

for idx, (text, tag) in enumerate(SAMPLES, 1):
    lines = []
    lines.append(f"\n### [{idx}] {text} — *{tag}*\n")

    for label in ("地名", "机构", "POI"):
        lines.append(f"| 版本 | {label}识别 |")
        lines.append("|------|" + "-" * 60 + "|")
        for ver in VERSIONS:
            pipe = PIPES[ver]
            r = pipe.recognize(text)
            if label == "POI" and r["poi"] is None:
                seg_str = "(skip - company suffix)"
            else:
                key = "loc" if label == "地名" else ("org" if label == "机构" else "poi")
                segs = r[key]["segments"]
                seg_str = " | ".join(f"[{s['type']}]「{s['text']}」" for s in segs)
            lines.append(f"| {ver} | {seg_str} |")
        lines.append("")

    report_lines.extend(lines)
    print(f"  [{idx:2d}] {text[:30]}... done")

with open(os.path.join(OUT_DIR, "samples", "samples_comparison.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(report_lines))

print(f"  Saved: {os.path.join(OUT_DIR, 'samples', 'samples_comparison.md')}")
print()

# ══════════════════════════════════════════════════════════════
# PART 3: 差异统计 (大量采样)
# ══════════════════════════════════════════════════════════════
print("=" * 60)
print("PART 3: 差异统计")
print("=" * 60)

from loc.recognizer import AddressRecognizer
from loc.builder import DictBuilder
from org.recognizer import OrgDPRecognizer
from poi.recognizer import PoiRecognizer

def sample_reservoir(filepath, n, encoding="utf-8", seed=42):
    random.seed(seed)
    reservoir = []
    k = 0
    for enc in ([encoding] if isinstance(encoding, str) else [encoding]):
        try:
            with open(filepath, encoding=enc, errors="replace") as f:
                for line in f:
                    text = line.strip()
                    if not text: continue
                    if k < n: reservoir.append(text)
                    else:
                        r = random.randint(0, k)
                        if r < n: reservoir[r] = text
                    k += 1
        except (UnicodeDecodeError, UnicodeError):
            continue
    return reservoir

def segment_signature(result):
    return tuple((s["type"], s["text"]) for s in result["segments"])

# --- 地名 ---
print("\n--- 地名 (loc) ---")
loc_recognizers = {}
for ver in VERSIONS:
    b = DictBuilder.load(DICT_DIR, f"loc_{ver}")
    loc_recognizers[ver] = AddressRecognizer(b.dict_data)

TEST_FILE = os.path.join(DATA_DIR, "地名T（7200w）input.txt")
samples = sample_reservoir(TEST_FILE, 2000, "gbk")
print(f"  Sampling: {len(samples)} entries from 地名T")

loc_sigs = {}
for ver in VERSIONS:
    loc_sigs[ver] = []
    for t in samples:
        res = loc_recognizers[ver].recognize(t)
        loc_sigs[ver].append(segment_signature(res.to_dict()))
    print(f"  {ver}: done")

loc_same = sum(1 for i in range(len(samples)) if loc_sigs["v1.1.0"][i] == loc_sigs["v1.1.1"][i] == loc_sigs["v1.1.2"][i])
loc_diff_01_02 = sum(1 for i in range(len(samples)) if loc_sigs["v1.1.0"][i] != loc_sigs["v1.1.1"][i] or loc_sigs["v1.1.1"][i] != loc_sigs["v1.1.2"][i])
loc_diff_01 = sum(1 for i in range(len(samples)) if loc_sigs["v1.1.0"][i] != loc_sigs["v1.1.1"][i])
loc_diff_12 = sum(1 for i in range(len(samples)) if loc_sigs["v1.1.1"][i] != loc_sigs["v1.1.2"][i])
loc_diff_examples = []
for i in range(len(samples)):
    if loc_sigs["v1.1.1"][i] != loc_sigs["v1.1.2"][i]:
        loc_diff_examples.append((samples[i], loc_sigs["v1.1.1"][i], loc_sigs["v1.1.2"][i]))
        if len(loc_diff_examples) >= 10: break

print(f"  三版一致: {loc_same}/{len(samples)} ({100*loc_same/len(samples):.1f}%)")
print(f"  至少两版不同: {loc_diff_01_02}")
print(f"    v1.1.0≠v1.1.1: {loc_diff_01}")
print(f"    v1.1.1≠v1.1.2: {loc_diff_12}")

# --- 机构名 ---
print("\n--- 机构名 (org) ---")
org_recognizers = {}
for ver in VERSIONS:
    org_recognizers[ver] = OrgDPRecognizer(DATA_DIR, version=ver)

ORG_FILE = os.path.join(DATA_DIR, "公司名input.txt")
org_samples = sample_reservoir(ORG_FILE, 500, "gbk")
print(f"  Sampling: {len(org_samples)} entries from 公司名input")

org_sigs = {}
for ver in VERSIONS:
    org_sigs[ver] = []
    for t in org_samples:
        res = org_recognizers[ver].recognize(t)
        org_sigs[ver].append(segment_signature(res.to_dict()))
    print(f"  {ver}: done")

org_same = sum(1 for i in range(len(org_samples)) if org_sigs["v1.1.0"][i] == org_sigs["v1.1.1"][i] == org_sigs["v1.1.2"][i])
org_diff_01 = sum(1 for i in range(len(org_samples)) if org_sigs["v1.1.0"][i] != org_sigs["v1.1.1"][i])
org_diff_12 = sum(1 for i in range(len(org_samples)) if org_sigs["v1.1.1"][i] != org_sigs["v1.1.2"][i])
org_diff_examples = []
for i in range(len(org_samples)):
    if org_sigs["v1.1.1"][i] != org_sigs["v1.1.2"][i]:
        org_diff_examples.append((org_samples[i], org_sigs["v1.1.1"][i], org_sigs["v1.1.2"][i]))
        if len(org_diff_examples) >= 10: break

print(f"  三版一致: {org_same}/{len(org_samples)} ({100*org_same/len(org_samples):.1f}%)")
print(f"    v1.1.0≠v1.1.1: {org_diff_01}")
print(f"    v1.1.1≠v1.1.2: {org_diff_12}")

# --- POI ---
print("\n--- POI ---")
poi_recognizers = {}
for ver in VERSIONS:
    poi_recognizers[ver] = PoiRecognizer(DATA_DIR, dict_name=f"poi_{ver}.pkl")

POI_SPLIT = os.path.join(DATA_DIR, "split", "poi")
poi_samples_data = []
for fname in sorted(os.listdir(POI_SPLIT)):
    if not fname.startswith("chunk_"): continue
    with open(os.path.join(POI_SPLIT, fname)) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            parts = line.rsplit('\t', 1)
            poi_samples_data.append(parts[0] if len(parts) == 2 else line)
            if len(poi_samples_data) >= 5000: break
    if len(poi_samples_data) >= 5000: break
# reservoir sample from collected
random.seed(42)
random.shuffle(poi_samples_data)
poi_samples_data = poi_samples_data[:500]
poi_samples = []
for line in poi_samples_data:
    parts = line.rsplit('\t', 1)
    poi_samples.append(parts[0] if len(parts) == 2 else line)
print(f"  Sampling: {len(poi_samples)} entries from poi_deduped")

poi_sigs = {}
for ver in VERSIONS:
    poi_sigs[ver] = []
    for t in poi_samples:
        res = poi_recognizers[ver].recognize(t)
        poi_sigs[ver].append(segment_signature(res.to_dict()))
    print(f"  {ver}: done")

poi_same = sum(1 for i in range(len(poi_samples)) if poi_sigs["v1.1.0"][i] == poi_sigs["v1.1.1"][i] == poi_sigs["v1.1.2"][i])
poi_diff_01 = sum(1 for i in range(len(poi_samples)) if poi_sigs["v1.1.0"][i] != poi_sigs["v1.1.1"][i])
poi_diff_12 = sum(1 for i in range(len(poi_samples)) if poi_sigs["v1.1.1"][i] != poi_sigs["v1.1.2"][i])
poi_diff_examples = []
for i in range(len(poi_samples)):
    if poi_sigs["v1.1.1"][i] != poi_sigs["v1.1.2"][i]:
        poi_diff_examples.append((poi_samples[i], poi_sigs["v1.1.1"][i], poi_sigs["v1.1.2"][i]))
        if len(poi_diff_examples) >= 10: break

print(f"  三版一致: {poi_same}/{len(poi_samples)} ({100*poi_same/len(poi_samples):.1f}%)")
print(f"    v1.1.0≠v1.1.1: {poi_diff_01}")
print(f"    v1.1.1≠v1.1.2: {poi_diff_12}")

# ══════════════════════════════════════════════════════════════
# PART 4: 完整报告
# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("PART 4: 生成报告")
print("=" * 60)

report = []
report.append("# dict_ner v1.2.2 三维度三版本对比报告")
report.append(f"\n> 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
report.append("> 测试数据: 地名T(2000) + 公司名input(500) + poi_deduped(500)\n")

report.append("## 一、词典规模对比\n")
report.append("| 版本 | org d1 | org d3 | org d4 | poi d1 | poi d3 | poi d4 | brand bigrams |")
report.append("|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
for ver in VERSIONS:
    op = os.path.join(DICT_DIR, f"org_{ver}.pkl")
    pp = os.path.join(DICT_DIR, f"poi_{ver}.pkl")
    bp = os.path.join(DICT_DIR, f"brand_{ver}.pkl")
    od1 = od3 = od4 = pd1 = pd3 = pd4 = bb = "-"
    if os.path.exists(op):
        with open(op, "rb") as f:
            d = pickle.load(f); od1 = len(d["d1_freqs"]); od3 = len(d["d3_freqs"]); od4 = len(d["d4_freqs"])
    if os.path.exists(pp):
        with open(pp, "rb") as f:
            d = pickle.load(f); pd1 = len(d["d1_freqs"]); pd3 = len(d["d3_freqs"]); pd4 = len(d["d4_freqs"])
    if os.path.exists(bp):
        with open(bp, "rb") as f:
            d = pickle.load(f); bb = f"{len(d['bigram_counts']):,}"
    report.append(f"| {ver} | {od1:,} | {od3:,} | {od4:,} | {pd1:,} | {pd3:,} | {pd4:,} | {bb} |")

report.append("\n> 词典 top-50 高频词详见 `output/comparison/dicts/*.txt`\n")

report.append("## 二、识别差异统计\n")

report.append("### 2.1 地名模块 (2000条)\n")
report.append(f"- 三版完全一致: **{loc_same}** ({100*loc_same/len(samples):.1f}%)")
report.append(f"- v1.1.0 ≠ v1.1.1: {loc_diff_01} 条")
report.append(f"- v1.1.1 ≠ v1.1.2: {loc_diff_12} 条")
if loc_diff_examples:
    report.append("\n**v1.1.1→v1.1.2 不一致样例**:\n")
    for text, sig1, sig2 in loc_diff_examples[:5]:
        report.append(f"- 「{text}」")
        report.append(f"  - v1.1.1: {' | '.join(f'[{t}]「{w}」' for t,w in sig1)}")
        report.append(f"  - v1.1.2: {' | '.join(f'[{t}]「{w}」' for t,w in sig2)}")

report.append("\n### 2.2 机构名模块 (500条)\n")
report.append(f"- 三版完全一致: **{org_same}** ({100*org_same/len(org_samples):.1f}%)")
report.append(f"- v1.1.0 ≠ v1.1.1: {org_diff_01} 条")
report.append(f"- v1.1.1 ≠ v1.1.2: {org_diff_12} 条")
if org_diff_examples:
    report.append("\n**v1.1.1→v1.1.2 不一致样例**:\n")
    for text, sig1, sig2 in org_diff_examples[:5]:
        report.append(f"- 「{text}」")
        report.append(f"  - v1.1.1: {' | '.join(f'[{t}]「{w}」' for t,w in sig1)}")
        report.append(f"  - v1.1.2: {' | '.join(f'[{t}]「{w}」' for t,w in sig2)}")

report.append("\n### 2.3 POI模块 (500条)\n")
report.append(f"- 三版完全一致: **{poi_same}** ({100*poi_same/len(poi_samples):.1f}%)")
report.append(f"- v1.1.0 ≠ v1.1.1: {poi_diff_01} 条")
report.append(f"- v1.1.1 ≠ v1.1.2: {poi_diff_12} 条")
if poi_diff_examples:
    report.append("\n**v1.1.1→v1.1.2 不一致样例**:\n")
    for text, sig1, sig2 in poi_diff_examples[:5]:
        report.append(f"- 「{text}」")
        report.append(f"  - v1.1.1: {' | '.join(f'[{t}]「{w}」' for t,w in sig1)}")
        report.append(f"  - v1.1.2: {' | '.join(f'[{t}]「{w}」' for t,w in sig2)}")

report.append("\n## 三、版本质量评分 (eval.py)\n")
report.append("| 版本 | 未知字符率 | 有效转移率 | 质量分 |")
report.append("|------|:---:|:---:|:---:|")
for ver in VERSIONS:
    b = DictBuilder.load(DICT_DIR, f"loc_{ver}")
    r = AddressRecognizer(b.dict_data)
    stats = {"unknown_chars": 0, "total_chars": 0, "valid_transitions": 0, "invalid_transitions": 0}
    from core.types import SegType
    VALID = {
        (SegType.PROVINCE, SegType.CITY), (SegType.CITY, SegType.DISTRICT),
        (SegType.CITY, SegType.TOWN), (SegType.DISTRICT, SegType.TOWN),
        (SegType.DISTRICT, SegType.ROAD), (SegType.TOWN, SegType.VILLAGE),
        (SegType.TOWN, SegType.COMMUNITY), (SegType.TOWN, SegType.ROAD),
        (SegType.VILLAGE, SegType.ROAD), (SegType.COMMUNITY, SegType.ROAD),
        (SegType.ROAD, SegType.POI), (SegType.ROAD, SegType.LOCATION),
        (SegType.ROAD, SegType.ORIENTATION), (SegType.POI, SegType.LOCATION),
        (SegType.POI, SegType.ORIENTATION), (SegType.ORIENTATION, SegType.LOCATION),
        (SegType.ORIENTATION, SegType.ROAD),
    }
    for t in samples:
        res = r.recognize(t)
        for seg in res.segments:
            stats["total_chars"] += len(seg.text)
            if seg.seg_type in (SegType.UNKNOWN, SegType.CHAR):
                stats["unknown_chars"] += len(seg.text)
        for i in range(len(res.segments) - 1):
            a = res.segments[i].seg_type; b = res.segments[i + 1].seg_type
            if (a, b) in VALID: stats["valid_transitions"] += 1
            else: stats["invalid_transitions"] += 1
    ur = 100 * stats["unknown_chars"] / max(1, stats["total_chars"])
    tt = stats["valid_transitions"] + stats["invalid_transitions"]
    vr = 100 * stats["valid_transitions"] / max(1, tt)
    score = max(0, 100 - ur * 1.5 - (100 - vr) * 0.5)
    report.append(f"| {ver} | {ur:.1f}% | {vr:.1f}% | {score:.1f} |")

report.append("\n## 四、结论\n")
# Determine best version
b = DictBuilder.load(DICT_DIR, "loc_v1.1.2")
r = AddressRecognizer(b.dict_data)
stats = {"uc": 0, "tc": 0, "vt": 0, "it": 0}
for t in samples:
    res = r.recognize(t)
    for seg in res.segments:
        stats["tc"] += len(seg.text)
        if seg.seg_type in (SegType.UNKNOWN, SegType.CHAR): stats["uc"] += len(seg.text)
    for i in range(len(res.segments) - 1):
        a = res.segments[i].seg_type; b = res.segments[i + 1].seg_type
        if (a, b) in VALID: stats["vt"] += 1
        else: stats["it"] += 1
cur_ur = 100 * stats["uc"] / max(1, stats["tc"])
cur_tt = stats["vt"] + stats["it"]
cur_vr = 100 * stats["vt"] / max(1, cur_tt)
cur_s = max(0, 100 - cur_ur * 1.5 - (100 - cur_vr) * 0.5)

report.append(f"v1.2.2 (词典 v1.1.2) 在地名识别质量上达到 **{cur_s:.1f}/100**。")
if loc_diff_12 > 0:
    report.append(f"与 v1.1.1 存在 **{loc_diff_12}/{len(samples)} ({100*loc_diff_12/len(samples):.1f}%)** 地名输出差异，")
    report.append(f"机构名差异 {org_diff_12}/{len(org_samples)} ({100*org_diff_12/len(org_samples):.1f}%)，")
    report.append(f"POI差异 {poi_diff_12}/{len(poi_samples)} ({100*poi_diff_12/len(poi_samples):.1f}%)。")
    report.append(f"差异主要由 POI后缀词库合并 (80+119→131条) 和 LOCATION 重复扫描修复导致。")
report.append(f"\n详细样本对比见 `output/comparison/samples/samples_comparison.md`")
report.append(f"词典 top-N 见 `output/comparison/dicts/`")

with open(os.path.join(OUT_DIR, "report.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(report))

print(f"  Saved: {os.path.join(OUT_DIR, 'report.md')}")
print(f"\nDone! All output in: {OUT_DIR}")
