#!/usr/bin/env python3
"""POI data: dedup A+T with frequency weighting"""
import os, sys, csv as csv_mod
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "data")

COMPANY_SUFFIXES = [
    '公司', '有限公司', '有限责任公司', '股份有限公司',
    '集团', '企业', '总公司', '分公司', '子公司',
]


def load_area_set() -> set:
    area_set = set()
    areas_dir = os.path.join(DATA_DIR, "areas")
    for fname in ['provinces.csv', 'cities.csv', 'areas.csv', 'streets.csv', 'villages.csv']:
        path = os.path.join(areas_dir, fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf-8-sig') as f:
            for row in csv_mod.DictReader(f):
                name = row.get('name', '').strip()
                if name and len(name) >= 2:
                    area_set.add(name)
    return area_set


def is_place(text: str, area_set: set) -> bool:
    return text in area_set


def is_company(text: str) -> bool:
    for sfx in COMPANY_SUFFIXES:
        if text.endswith(sfx) and len(text) > len(sfx):
            return True
    return False


def main():
    out = sys.argv[1]
    sources = sys.argv[2:] or [os.path.join(DATA_DIR, "兴趣点A（6500w）input.txt"),
                                os.path.join(DATA_DIR, "兴趣点T（7200w）input.txt")]

    found = [s for s in sources if os.path.exists(s)]
    if not found:
        print(f"ERROR: No POI source files found.")
        for s in sources:
            print(f"  Missing: {s}")
        sys.exit(1)

    area_set = load_area_set()
    print(f"Loaded {len(area_set):,} area names")

    counter = Counter()
    total = 0
    place_exc = 0
    comp_exc = 0
    short_exc = 0

    for src in sources:
        if not os.path.exists(src):
            print(f"  SKIP: {src}")
            continue
        print(f"  Counting: {os.path.basename(src)}...")
        with open(src, 'r', encoding='gbk', errors='replace') as f:
            for line in f:
                text = line.strip()
                if not text or len(text) < 2:
                    short_exc += 1
                    continue
                total += 1

                if is_place(text, area_set):
                    place_exc += 1
                    continue
                if is_company(text):
                    comp_exc += 1
                    continue

                counter[text] += 1

                if total % 5000000 == 0:
                    print(f'    {total//10000:>4}w  unique={len(counter):,}', flush=True)

    with open(out, 'w', encoding='utf-8') as f:
        for text, freq in counter.most_common():
            f.write(f"{text}\t{freq}\n")

    mb = os.path.getsize(out) / 1024 / 1024
    print(f'\n=== Dedup done ===')
    print(f'  Raw total:     {total:>12,}')
    print(f'  Place excl:    {place_exc:>12,} ({100*place_exc/max(1,total):.1f}%)')
    print(f'  Company excl:  {comp_exc:>12,} ({100*comp_exc/max(1,total):.1f}%)')
    print(f'  Deduped POI:   {len(counter):>12,} ({100*len(counter)/max(1,total):.1f}%)')
    print(f'  Saved: {out} ({mb:.0f}MB)')


if __name__ == '__main__':
    main()
