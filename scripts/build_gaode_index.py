#!/usr/bin/env python3
"""Single-pass scan Gaode 67 files → suffix_category_gaode.csv + d4_category_map.pkl + gaode_roads.csv"""
import csv
import os
import pickle
import re
import sys
from collections import Counter, defaultdict

csv.field_size_limit(100 * 1024 * 1024)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAODE_DIR = os.path.join(BASE, "data", "高德amap")
DICT_DIR = os.path.join(BASE, "dicts")
DATA_DIR = os.path.join(BASE, "data")

TYPE_TO_CLASS = {
    "公司企业": "ORG", "政府机构及社会团体": "ORG",
    "金融保险服务": "ORG", "科教文化服务": "ORG",
    "医疗保健服务": "ORG",
    "交通设施服务": "POI_FAC", "公共设施": "POI_FAC",
    "道路附属设施": "POI_FAC", "通行设施": "POI_FAC",
    "购物服务": "POI_STORE", "餐饮服务": "POI_STORE",
    "住宿服务": "POI_STORE", "生活服务": "POI_STORE",
    "体育休闲服务": "POI_STORE", "汽车维修": "POI_STORE",
    "汽车服务": "POI_STORE", "汽车销售": "POI_STORE",
    "摩托车服务": "POI_STORE", "旅游服务": "POI_STORE",
    "商务住宅": "ADDR", "地名地址信息": "ADDR", "风景名胜": "ADDR",
}

ROAD_RE = re.compile(r"([\u4e00-\u9fa5]{2,6}(?:路|街|道|巷|弄|胡同|大街|大道|环路))")


def load_org_d4():
    path = os.path.join(DICT_DIR, "org_v1.2.2.pkl")
    if not os.path.exists(path):
        path = os.path.join(DICT_DIR, "org_v1.1.2.pkl")
    with open(path, "rb") as f:
        return set(pickle.load(f).get("d4_freqs", {}).keys())


def main():
    org_d4_set = load_org_d4()
    print(f"Loaded org d4: {len(org_d4_set):,} suffixes", flush=True)

    suffix_type_freq = defaultdict(lambda: Counter())
    d4_type_dist = defaultdict(lambda: Counter())
    road_freq = Counter()
    natural_names = Counter()
    total_rows = 0
    org_d4_maxlen = max(len(d) for d in org_d4_set) if org_d4_set else 8

    files = sorted([f for f in os.listdir(GAODE_DIR) if f.endswith(".csv")])
    print(f"\nScanning {len(files)} Gaode files...", flush=True)

    for fi, fname in enumerate(files):
        path = os.path.join(GAODE_DIR, fname)
        file_rows = 0
        with open(path, encoding="gbk", errors="replace") as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                if len(row) < 10:
                    continue
                name = (row[6] or "").strip()
                typ = (row[9] or "").strip()
                addr = (row[0] or "").strip()
                if not name or len(name) < 2 or name.isdigit():
                    continue
                file_rows += 1

                parts = [p for p in typ.split(";") if p]
                t1 = parts[0] if len(parts) > 0 else ""

                for slen in range(min(4, len(name)), 1, -1):
                    sfx = name[-slen:]
                    suffix_type_freq[sfx][t1] += 1
                    break

                for slen in range(min(org_d4_maxlen, len(name)), 1, -1):
                    d4 = name[-slen:]
                    if d4 in org_d4_set:
                        d4_type_dist[d4][t1] += 1
                        break

                if t1 == "地名地址信息" and len(parts) >= 3 and parts[1] == "自然地名":
                    natural_names[name] += 1

                for m in ROAD_RE.finditer(addr):
                    road = m.group(1)
                    if not any(c.isdigit() for c in road):
                        road_freq[road] += 1

        total_rows += file_rows
        if (fi + 1) % 10 == 0:
            print(f"  [{fi + 1}/{len(files)}] {total_rows:,} rows", flush=True)

    print(f"\nScan complete: {total_rows:,} rows from {len(files)} files", flush=True)

    # --- Output 1: suffix_category_gaode.csv ---
    print("\nBuilding suffix_category_gaode.csv...", flush=True)
    sql_suffixes = set()
    sql_path = os.path.join(DATA_DIR, "suffix_segments_sql.csv")
    with open(sql_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            sfx = row["d4"].strip()
            if sfx and len(sfx) >= 2:
                sql_suffixes.add(sfx)

    suffix_entries = []
    for sfx, type_counts in suffix_type_freq.items():
        total = sum(type_counts.values())
        if total < 500 or sfx not in sql_suffixes:
            continue
        dom_type = type_counts.most_common(1)[0][0]
        dom_count = type_counts.most_common(1)[0][1]
        gaode_conf = dom_count / total
        cat = TYPE_TO_CLASS.get(dom_type)
        if cat is None:
            continue
        if gaode_conf < 0.90:
            continue
        suffix_entries.append((sfx, cat, gaode_conf, total, dom_type))

    suffix_entries.sort(key=lambda x: -x[3])
    out_csv = os.path.join(DICT_DIR, "suffix_category_gaode.csv")
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["suffix", "gaode_category", "gaode_confidence", "gaode_freq", "dom_type"])
        for sfx, cat, conf, freq, dom in suffix_entries:
            writer.writerow([sfx, cat, round(conf, 4), freq, dom])
        writer.writerow(["店", "POI_STORE", 1.0, 500000, "购物服务"])
        writer.writerow(["馆", "POI_STORE", 1.0, 500000, "餐饮服务"])

    cat_counts = Counter(c for _, c, _, _, _ in suffix_entries)
    print(f"  Wrote {len(suffix_entries)} entries: "
          f"ORG={cat_counts.get('ORG',0)} POI_FAC={cat_counts.get('POI_FAC',0)} "
          f"POI_STORE={cat_counts.get('POI_STORE',0)} ADDR={cat_counts.get('ADDR',0)}", flush=True)

    # --- Output 2: d4_category_map.pkl ---
    print("\nBuilding d4_category_map.pkl...", flush=True)
    d4_map = {}
    stats = Counter()
    for d4 in sorted(org_d4_set):
        type_counts = d4_type_dist.get(d4, Counter())
        total = sum(type_counts.values())
        if total < 5:
            d4_map[d4] = {"category": "UNKNOWN", "confidence": 0.0, "gaode_freq": total, "dom_type": ""}
            stats["UNKNOWN"] += 1
            continue

        dom_type = type_counts.most_common(1)[0][0]
        dom_count = type_counts.most_common(1)[0][1]
        ratio = dom_count / total
        cat = TYPE_TO_CLASS.get(dom_type)

        if cat and ratio >= 0.80:
            final_cat = cat
            final_conf = ratio
        elif cat and ratio >= 0.60:
            final_cat = "AMBIGUOUS"
            final_conf = ratio
        elif cat is not None:
            final_cat = "AMBIGUOUS"
            final_conf = ratio
        else:
            final_cat = "UNKNOWN"
            final_conf = 0.0

        d4_map[d4] = {
            "category": final_cat, "confidence": round(final_conf, 4),
            "gaode_freq": total, "dom_type": dom_type,
        }
        stats[final_cat] += 1

    out_pkl = os.path.join(DICT_DIR, "d4_category_map.pkl")
    with open(out_pkl, "wb") as f:
        pickle.dump(d4_map, f)

    print(f"  Wrote {len(d4_map):,} entries: "
          f"ORG={stats.get('ORG',0)} POI_FAC={stats.get('POI_FAC',0)} "
          f"POI_STORE={stats.get('POI_STORE',0)} ADDR={stats.get('ADDR',0)} "
          f"AMBIGUOUS={stats.get('AMBIGUOUS',0)} UNKNOWN={stats.get('UNKNOWN',0)}", flush=True)

    # --- Output 3: gaode_roads.csv ---
    print("\nBuilding gaode_roads.csv...", flush=True)
    roads_filtered = {r: c for r, c in road_freq.items() if c >= 3}
    out_roads = os.path.join(DATA_DIR, "gaode_roads.csv")
    with open(out_roads, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["road_name", "freq"])
        for road, cnt in sorted(roads_filtered.items(), key=lambda x: -x[1]):
            writer.writerow([road, cnt])

    print(f"  Wrote {len(roads_filtered):,} roads (freq>=3)", flush=True)
    print(f"  Natural names collected: {len(natural_names):,}", flush=True)


if __name__ == "__main__":
    main()
