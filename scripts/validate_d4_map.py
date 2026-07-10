#!/usr/bin/env python3
"""Validate d4_category_map.pkl against suffix_segments_sql.csv"""
import csv
import os
import pickle
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_DIR = os.path.join(BASE, "dicts")
DATA_DIR = os.path.join(BASE, "data")

D4_MAP_PATH = os.path.join(DICT_DIR, "d4_category_map.pkl")
SQL_CSV_PATH = os.path.join(DATA_DIR, "suffix_segments_sql.csv")


def load_sql_csv():
    sql = {}
    with open(SQL_CSV_PATH, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            sfx = row["d4"].strip()
            if not sfx or len(sfx) < 2:
                continue
            try:
                com = int(row.get("com", 0) or 0)
                org = int(row.get("org", 0) or 0)
                loc = int(row.get("loc", 0) or 0)
            except (ValueError, KeyError):
                continue
            total = com + org + loc
            if total == 0:
                continue
            sql[sfx] = {
                "com": com, "org": org, "loc": loc, "total": total,
                "org_ratio": org / total, "loc_ratio": loc / total,
            }
    return sql


def sql_infer(sql_entry):
    r = sql_entry
    if r["org_ratio"] >= 0.6:
        return "ORG"
    if r["loc_ratio"] >= 0.6:
        return "LOC"
    if r["org"] >= 2 * max(r["loc"], r["com"]) or r["loc"] >= 2 * max(r["org"], r["com"]):
        return "ORG" if r["org"] >= 2 * max(r["loc"], r["com"]) else "LOC"
    return "MIXED"


def category_simplify(cat):
    if cat in ("ORG",):
        return "ORG"
    if cat in ("POI_FAC", "POI_STORE"):
        return "POI"
    if cat in ("ADDR",):
        return "LOC"
    return "OTHER"


def check_agreement(gaode_cat, sql_infer_cat, sql_entry):
    gaode_simple = category_simplify(gaode_cat)
    if sql_infer_cat == "MIXED":
        return "WEAK_AGREE"
    if gaode_cat in ("AMBIGUOUS", "UNKNOWN"):
        return "NEUTRAL"
    if gaode_simple == sql_infer_cat:
        return "STRONG_AGREE"
    return "CONFLICT"


def main():
    with open(D4_MAP_PATH, "rb") as f:
        d4_map = pickle.load(f)
    sql = load_sql_csv()

    results = []
    agreement = Counter()
    conflicts = []

    for sfx, entry in d4_map.items():
        gaode_cat = entry.get("category", "UNKNOWN")
        gaode_freq = entry.get("gaode_freq", 0)
        sql_entry = sql.get(sfx)

        if sql_entry is None:
            agreement["UNTESTABLE"] += 1
            continue

        sql_infer_cat = sql_infer(sql_entry)
        agree = check_agreement(gaode_cat, sql_infer_cat, sql_entry)
        agreement[agree] += 1
        results.append((sfx, gaode_cat, gaode_freq, sql_infer_cat, agree,
                        sql_entry["org_ratio"], sql_entry["loc_ratio"]))

        if agree == "CONFLICT":
            conflicts.append((sfx, gaode_cat, sql_infer_cat, gaode_freq,
                            sql_entry["org_ratio"], sql_entry["loc_ratio"]))

    total = len(d4_map)
    print(f"d4_category_map.pkl: {total:,} entries")
    print(f"SQL CSV: {len(sql):,} suffixes")
    print()
    print("=== Agreement Distribution ===")
    for k in ("STRONG_AGREE", "WEAK_AGREE", "NEUTRAL", "CONFLICT", "UNTESTABLE"):
        c = agreement.get(k, 0)
        print(f"  {k:<15s}: {c:>6} ({c*100/max(1,total):.1f}%)")

    testable = total - agreement.get("UNTESTABLE", 0)
    conflict_rate = agreement.get("CONFLICT", 0) / max(1, testable) * 100
    print(f"\n  Conflict rate (of testable): {conflict_rate:.1f}%")

    if conflicts:
        conflicts.sort(key=lambda x: -x[3])
        print(f"\n=== Top 30 Conflicts ===")
        print(f"  {'suffix':<16s} {'gage_cat':>12s} {'sql_infer':>12s} {'gage_freq':>10s} {'org_ratio':>10s} {'loc_ratio':>10s}")
        for sfx, gc, si, freq, org_r, loc_r in conflicts[:30]:
            print(f"  {sfx:<16s} {gc:>12s} {si:>12s} {freq:>10,} {org_r:>10.4f} {loc_r:>10.4f}")


if __name__ == "__main__":
    main()
