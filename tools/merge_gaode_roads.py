#!/usr/bin/env python3
"""Merge Gaode road names into LOC dictionary → loc_v1.2.1.pkl"""
import os
import sys
import pickle
import csv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.types import SegType

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_DIR = os.path.join(BASE, "dicts")
ROADS_CSV = os.path.join(BASE, "data", "gaode_roads.csv")


def main():
    src = os.path.join(DICT_DIR, "loc_v1.2.0.pkl")
    dst = os.path.join(DICT_DIR, "loc_v1.2.1.pkl")

    with open(src, "rb") as f:
        data = pickle.load(f)

    road_dict = data.get(SegType.ROAD, {})
    if not isinstance(road_dict, dict):
        road_dict = {}
    all_words = set()
    for seg_type, words in data.items():
        if isinstance(words, dict):
            all_words.update(words.keys())

    added = 0
    skipped = 0
    with open(ROADS_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            road = row["road_name"].strip()
            if not road or len(road) < 2:
                continue
            if road in road_dict or road in all_words:
                skipped += 1
                continue
            road_dict[road] = max(50, int(row.get("freq", 3)))
            added += 1

    data[SegType.ROAD] = road_dict

    with open(dst, "wb") as f:
        pickle.dump(data, f)

    print(f"Merge complete: +{added} roads, {skipped} already existed")
    print(f"Saved: {dst} ({os.path.getsize(dst) / 1024 / 1024:.1f}MB)")
    print(f"ROAD entries: {len(road_dict):,}")


if __name__ == "__main__":
    main()
