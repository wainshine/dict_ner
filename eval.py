#!/usr/bin/env python3
"""评估脚本：从地名T采样 → 识别 → 统计 → 诊断"""
import os, sys, time, random, logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loc.builder import DictBuilder
from loc.recognizer import AddressRecognizer
from core.types import SegType, ADMIN_SUFFIX_MAP, POI_SUFFIX_MAP

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DICT_DIR = os.path.join(BASE_DIR, "dicts")

SAMPLE_SIZE = 5000
VERSION = os.environ.get("DICT_VERSION", "loc_v1.1.2")


def sample_from_gbk(filepath, n):
    reservoir = []
    t0 = time.time()
    k = 0
    with open(filepath, "r", encoding="gbk", errors="replace") as f:
        for line in f:
            text = line.strip()
            if not text:
                continue
            if k < n:
                reservoir.append(text)
            else:
                r = random.randint(0, k)
                if r < n:
                    reservoir[r] = text
            k += 1
            if k % 10000000 == 0:
                print(f"    Sampling... {k//10000}w non-empty lines")
    print(f"  Sampled {len(reservoir):,} in {time.time()-t0:.1f}s (from {k:,} total)")
    return reservoir


def evaluate(recognizer, samples):
    results = []
    stats = {
        "total": 0,
        "segments_dist": Counter(),
        "type_counts_raw": Counter(),
        "type_counts_norm": Counter(),
        "unknown_chars": 0,
        "total_chars": 0,
        "valid_transitions": 0,
        "invalid_transitions": 0,
        "correctable": defaultdict(list),
    }

    VALID_TRANSITIONS = {
        (SegType.PROVINCE, SegType.CITY),
        (SegType.PROVINCE, SegType.DISTRICT),
        (SegType.CITY, SegType.DISTRICT),
        (SegType.CITY, SegType.TOWN),
        (SegType.DISTRICT, SegType.TOWN),
        (SegType.DISTRICT, SegType.ROAD),
        (SegType.DISTRICT, SegType.VILLAGE),
        (SegType.TOWN, SegType.VILLAGE),
        (SegType.TOWN, SegType.COMMUNITY),
        (SegType.TOWN, SegType.ROAD),
        (SegType.TOWN, SegType.POI),
        (SegType.VILLAGE, SegType.ROAD),
        (SegType.VILLAGE, SegType.POI),
        (SegType.COMMUNITY, SegType.ROAD),
        (SegType.COMMUNITY, SegType.POI),
        (SegType.ROAD, SegType.POI),
        (SegType.ROAD, SegType.ORIENTATION),
        (SegType.ROAD, SegType.LOCATION),
        (SegType.POI, SegType.LOCATION),
        (SegType.POI, SegType.ORIENTATION),
        (SegType.ORIENTATION, SegType.ROAD),
        (SegType.ORIENTATION, SegType.LOCATION),
    }

    for text in samples:
        res = recognizer.recognize(text)
        results.append(res)
        stats["total"] += 1

        n_segs = len(res.segments)
        stats["segments_dist"][n_segs] += 1

        types_here = set()
        for seg in res.segments:
            stats["total_chars"] += len(seg.text)
            if seg.seg_type in (SegType.UNKNOWN, SegType.CHAR):
                stats["unknown_chars"] += len(seg.text)
                if seg.text:
                    stats["correctable"]["has_unknown"].append((text, seg.text))
            key = seg.seg_type.value
            stats["type_counts_raw"][key] += 1
            if key not in types_here:
                stats["type_counts_norm"][key] += 1
                types_here.add(key)

        for i in range(len(res.segments) - 1):
            a, b = res.segments[i].seg_type, res.segments[i + 1].seg_type
            if (a, b) in VALID_TRANSITIONS:
                stats["valid_transitions"] += 1
            else:
                stats["invalid_transitions"] += 1
                stats["correctable"]["bad_transition"].append(
                    (text, f"{a.value}→{b.value}")
                )

        if len(res.segments) == 1 and res.segments[0].seg_type == SegType.ROAD:
            seg = res.segments[0]
            has_internal = _has_internal_structure(seg.text)
            if has_internal:
                stats["correctable"]["compound_road"].append((text, has_internal))

        if len(res.segments) >= 2:
            last = res.segments[-1]
            prev = res.segments[-2]
            if last.seg_type == SegType.UNKNOWN and prev.seg_type not in (SegType.UNKNOWN, SegType.CHAR):
                stats["correctable"]["trailing_unknown"].append(
                    (text, f"{prev.seg_type.value}→{last.text}")
                )

    return results, stats


def _has_internal_structure(text):
    indicators = []
    for stype, suffixes in ADMIN_SUFFIX_MAP.items():
        for sfx in suffixes:
            if len(sfx) >= 2 and sfx in text:
                pos = text.find(sfx)
                if text.endswith(sfx) and pos == len(text) - len(sfx):
                    continue
                indicators.append(sfx)
    for sfx in POI_SUFFIX_MAP:
        if len(sfx) >= 2 and sfx in text:
            indicators.append(sfx)
    return indicators[:5] if indicators else []


def print_report(stats):
    total = stats["total"]
    print()
    print("=" * 60)
    print("EVALUATION REPORT")
    print("=" * 60)

    print(f"\nSamples: {total:,}")
    print(f"Avg segments: {sum(k*v for k,v in stats['segments_dist'].items())/total:.2f}")

    print(f"\n--- Segment Distribution ---")
    for n in sorted(stats["segments_dist"]):
        print(f"  {n} segments: {stats['segments_dist'][n]:>6,} "
              f"({100*stats['segments_dist'][n]/total:.1f}%)")

    print(f"\n--- Type Distribution (doc-level, normalized) ---")
    for typ, cnt in stats["type_counts_norm"].most_common(15):
        print(f"  {typ:20s}: {cnt:>6,} ({100*cnt/total:.1f}%)")

    print(f"\n--- Quality Metrics ---")
    unknown_rate = 100 * stats["unknown_chars"] / max(1, stats["total_chars"])
    print(f"  Unknown char rate:  {unknown_rate:.1f}% (lower is better)")

    total_trans = stats["valid_transitions"] + stats["invalid_transitions"]
    valid_rate = 0.0
    if total_trans > 0:
        valid_rate = 100 * stats["valid_transitions"] / total_trans
        print(f"  Valid transitions:  {valid_rate:.1f}% (higher is better)")
    else:
        print(f"  Valid transitions:  N/A (no transitions)")

    # Quality score: penalties for unknown chars (weight 1.5) and invalid transitions (weight 0.5)
    # Max score 100. Unknown char rate penalized harder than bad transitions.
    score = max(0, 100 - unknown_rate * 1.5 - (100 - valid_rate) * 0.5)
    print(f"  Quality score:      {score:.1f}/100")

    print(f"\n--- Correctable Issues ---")
    for issue, cases in stats["correctable"].items():
        n = len(cases)
        if n > 0:
            print(f"  {issue}: {n} cases")
            for text, detail in cases[:3]:
                print(f"    「{text}」→ {detail}")
            if len(cases) > 3:
                print(f"    ... and {len(cases)-3} more")

    print()
    return score


def main():
    test_file = os.path.join(BASE_DIR, "data", "地名T（7200w）input.txt")
    if not os.path.exists(test_file):
        print(f"Test file not found: {test_file}")
        sys.exit(1)

    print(f"Sampling {SAMPLE_SIZE} from 地名T...")
    t0 = time.time()
    samples = sample_from_gbk(test_file, SAMPLE_SIZE)
    print(f"  Sampled {len(samples):,} in {time.time()-t0:.1f}s")

    print(f"Loading model ({VERSION})...")
    builder = DictBuilder.load(DICT_DIR, VERSION)
    recognizer = AddressRecognizer(builder.dict_data)

    print(f"Evaluating {len(samples):,} samples...")
    t0 = time.time()
    _, stats = evaluate(recognizer, samples)
    print(f"  Evaluated in {time.time()-t0:.1f}s")

    print_report(stats)


if __name__ == "__main__":
    main()
