#!/usr/bin/env python3
"""依据 areas/ 五级行政区划清理 LOC 词典中错误标记为 VILLAGE 的城市名/区划名"""
import os, sys, pickle, csv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.types import SegType

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AREAS_DIR = os.path.join(BASE, "data", "areas")
DICT_DIR = os.path.join(BASE, "dicts")


def main():
    cities = set()
    with open(os.path.join(AREAS_DIR, "cities.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row["name"].strip().strip('"')
            for sfx in ("市", "地区", "自治州", "盟"):
                if name.endswith(sfx):
                    bare = name[:-len(sfx)]
                    if len(bare) >= 2:
                        cities.add(bare)
            cities.add(name)

    all_villages = set()
    with open(os.path.join(AREAS_DIR, "villages.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row["name"].strip().strip('"')
            if len(name) >= 2:
                all_villages.add(name)

    src = os.path.join(DICT_DIR, "loc_v1.4.0_unbaked.pkl")
    with open(src, "rb") as f:
        data = pickle.load(f)

    village_dict = dict(data.get(SegType.VILLAGE, {}))
    city_dict = dict(data.get(SegType.CITY, {}))

    removed = []
    for word, freq in list(village_dict.items()):
        if word in cities and word not in all_villages:
            del village_dict[word]
            city_dict[word] = max(city_dict.get(word, 0), freq)
            removed.append((word, freq, "CITY"))

    for word, freq in list(village_dict.items()):
        for city_bare in cities:
            if word.startswith(city_bare) and len(word) == len(city_bare) + 1:
                suffix = word[-1]
                if suffix in "北南东西中上下左右前后":
                    del village_dict[word]
                    removed.append((word, freq, "CITY+ORIENTATION"))
                    break

    data[SegType.VILLAGE] = village_dict
    data[SegType.CITY] = city_dict

    dst = os.path.join(DICT_DIR, "loc_v1.4.0_unbaked.pkl")
    with open(dst, "wb") as f:
        pickle.dump(data, f)

    print(f"LOC VILLAGE cleanup: {len(removed)} entries removed")
    for word, freq, dest in removed[:20]:
        print(f"  {word} ({freq:,}) → {dest}")
    print(f"Saved: {dst} ({os.path.getsize(dst)/1024/1024:.1f}MB)")
    print(f"VILLAGE entries: {len(village_dict):,}")
    print(f"CITY entries: {len(city_dict):,}")


if __name__ == "__main__":
    main()
