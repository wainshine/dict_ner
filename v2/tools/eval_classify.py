#!/usr/bin/env python3
"""Evaluate classify performance → confusion matrix + per-class F1 + macro-F1"""
import argparse
import csv
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from pipeline_v2 import DictNerPipeline

from tools.metrics import LABELS, compute_metrics, print_metrics


def _baseline_classify(pipe, text):
    from core.types import SegType
    _GEO_SEG_TYPES = {
        SegType.PROVINCE, SegType.CITY, SegType.DISTRICT,
        SegType.TOWN, SegType.VILLAGE, SegType.COMMUNITY,
        SegType.ROAD, SegType.LOCATION, SegType.ORIENTATION,
    }
    org_res = pipe.org.recognize(text)
    if pipe._has_company_suffix(org_res):
        return "ORG"
    loc_res = pipe.loc.recognize(text)
    n = max(1, len(text))
    geo_cov = sum(len(s.text) for s in loc_res.segments
                  if s.seg_type in _GEO_SEG_TYPES) / n
    if geo_cov > 0.6:
        return "ADDR"
    poi_res = pipe.poi.recognize(text)
    if poi_res.segments:
        return "POI"
    return "UNKNOWN"


def evaluate(pipe, eval_path, use_baseline=False):
    results = []
    with open(eval_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = row["text"].strip()
            expected = row["label"].strip()
            if use_baseline:
                predicted = _baseline_classify(pipe, text)
            else:
                predicted = pipe.classify(text)["category"]
            results.append((expected, predicted))
    return results


def main():
    parser = argparse.ArgumentParser(description="Evaluate dict_ner classify performance")
    parser.add_argument("--eval", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                                       "data", "eval_set.csv"),
                        help="Path to eval set CSV")
    parser.add_argument("--baseline", default=None, help="Path to baseline JSON for comparison")
    parser.add_argument("--out", default=None, help="Path to save current result as JSON")
    parser.add_argument("--baseline-mode", action="store_true", help="Use v1.2.3 temporary classifier")
    args = parser.parse_args()

    pipe = DictNerPipeline()

    print(f"Evaluating: {args.eval}")
    print(f"Mode: {'baseline (v1.2.3 temp)' if args.baseline_mode else 'classify (v2.2.1.0)'}")

    t0 = time.time()
    results = evaluate(pipe, args.eval, use_baseline=args.baseline_mode)
    elapsed = time.time() - t0

    metrics = compute_metrics(results)
    print(f"\nTime: {elapsed:.1f}s")
    print()

    if args.baseline:
        with open(args.baseline, encoding="utf-8") as f:
            baseline = json.load(f)
        bm = baseline["metrics"]
        if "confusion_matrix" not in bm:
            cm = {exp: {pred: 0 for pred in LABELS} for exp in LABELS}
            cm_flat = baseline.get("confusion_matrix_flat") or bm.get("confusion_matrix_flat", {})
            for key, val in cm_flat.items():
                exp, pred = key.split("->")
                cm[exp][pred] = val
            bm["confusion_matrix"] = cm
        print_metrics(metrics, "=== Current ===")
        print()
        print_metrics(bm, "=== Baseline ===")
        print()
        print("=== Delta (current - baseline) ===")
        for lb in LABELS:
            cp = metrics["per_class"][lb]
            bp = baseline["metrics"]["per_class"][lb]
            df1 = cp["f1"] - bp["f1"]
            print(f"  {lb:>10s}:  "
                  f"precision {cp['precision']:.4f} ({cp['precision']-bp['precision']:+.4f})  "
                  f"recall {cp['recall']:.4f} ({cp['recall']-bp['recall']:+.4f})  "
                  f"f1 {cp['f1']:.4f} ({df1:+.4f})")
        dm = metrics["macro_f1"] - baseline["metrics"]["macro_f1"]
        print(f"\n  macro-F1 delta: {dm:+.4f}")
    else:
        print_metrics(metrics, "=== Results ===")

    if args.out:
        result = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "version": "v2.0.0",
            "eval_path": args.eval,
            "mode": "baseline" if args.baseline_mode else "classify",
            "metrics": {k: v for k, v in metrics.items() if k != "confusion_matrix"},
            "confusion_matrix_flat": {
                f"{exp}->{pred}": metrics["confusion_matrix"][exp][pred]
                for exp in LABELS for pred in LABELS
            },
        }
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\nSaved: {args.out}")


if __name__ == "__main__":
    main()
