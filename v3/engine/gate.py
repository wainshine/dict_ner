#!/usr/bin/env python3
"""统一引擎门禁 — 新 DPEngine vs 旧识别器 逐段一致性对比

用法: python v3/engine/gate.py [--n 20000] [--seed 42]
样本: eval_set.csv 随机抽样 n 条, 三体系逐一对比 (text, seg_type) 序列。
"""
import argparse
import csv
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def seg_sig(result):
    return [(s.text, s.seg_type.value) for s in result.segments]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    with open(os.path.join(BASE, "data", "eval_set.csv"), encoding="utf-8") as f:
        texts = [row["text"].strip() for row in csv.DictReader(f) if row["text"].strip()]
    random.seed(args.seed)
    texts = random.sample(texts, min(args.n, len(texts)))
    print(f"gate sample: {len(texts):,} texts")

    from v2.loc_builder import DictBuilder
    from v2.loc_recognizer import AddressRecognizer
    from v2.org_recognizer import OrgDPRecognizer
    from v2.poi_recognizer import PoiRecognizer
    from v3.engine.configs import build_loc_engine, build_org_engine, build_poi_engine

    pairs = []
    b = DictBuilder.load(os.path.join(BASE, "dicts"), "loc_v1.2.3")
    pairs.append(("loc", AddressRecognizer(b.dict_data), build_loc_engine()))
    pairs.append(("org", OrgDPRecognizer(os.path.join(BASE, "data"), version="v1.2.3"),
                  build_org_engine()))
    pairs.append(("poi", PoiRecognizer(os.path.join(BASE, "data"),
                                       dict_name="poi_v1.2.3.pkl"),
                  build_poi_engine()))

    total_bad = 0
    for name, legacy, new in pairs:
        bad = 0
        examples = []
        for t in texts:
            sig_old = seg_sig(legacy.recognize(t))
            sig_new = seg_sig(new.recognize(t))
            if sig_old != sig_new:
                bad += 1
                if len(examples) < 3:
                    examples.append((t, sig_old, sig_new))
        rate = bad / len(texts)
        status = "PASS" if rate < 0.005 else "FAIL"
        print(f"[{status}] {name}: diff {bad}/{len(texts)} ({rate:.4%})")
        for t, so, sn in examples:
            print(f"  text: {t}")
            print(f"    old: {so}")
            print(f"    new: {sn}")
        total_bad += bad

    sys.exit(0 if total_bad == 0 else 1)


if __name__ == "__main__":
    main()
