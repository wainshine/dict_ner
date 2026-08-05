#!/usr/bin/env python3
"""eval 集标签治理 — 修正 build_eval_set 两条错误映射 (v4.0.4, P2 诊断结论)

规则 (D0/P2 审计确认):
  R1: (tencent, 休闲娱乐, ADDR) → POI      # 足疗/洗浴/茶庄/采摘园 全是门店
  R2: (gaode, 风景名胜, ADDR) + 点位后缀 → POI  # 寺/庙/公园/景区类; 自然地名保持 ADDR

产出:
  data/eval_split_{train,val,test}.csv 原地修正 (备份 .bak_v1)
  output/v4_eval_label_fix.json  变更明细 (text→old/new), 供 feats CSV 标签列补丁用

用法: python3 v3/fix_eval_labels.py [--apply]
"""
import csv
import json
import os
import shutil
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
OUT_JSON = os.path.join(BASE, "output", "v4_eval_label_fix.json")

R2_POI_SUFFIX = (
    "寺", "庙", "庵", "祠", "公园", "景区", "风景区", "乐园", "植物园",
    "码头", "塔", "亭", "台", "楼", "阁", "苑", "园",
)


def load_type_orig():
    m = {}
    with open(os.path.join(DATA, "eval_set.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            m[r["text"]] = (r["source"], r["type_orig"])
    return m


def relabel(text, label, source, type_orig):
    """返回新标签 (无变更返回 None)"""
    if label != "ADDR":
        return None
    if source == "tencent" and type_orig == "休闲娱乐":
        return "POI"
    if source == "gaode" and type_orig == "风景名胜":
        if any(text.endswith(sfx) or sfx in text for sfx in R2_POI_SUFFIX):
            return "POI"
    return None


def main():
    apply = "--apply" in sys.argv
    type_map = load_type_orig()
    changes = {}
    for split in ("train", "val", "test"):
        path = os.path.join(DATA, f"eval_split_{split}.csv")
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        n_change = 0
        for r in rows:
            src, torig = type_map.get(r["text"], (r["source"], ""))
            new = relabel(r["text"], r["label"], src, torig)
            if new:
                changes[r["text"]] = {"old": r["label"], "new": new,
                                      "source": src, "type_orig": torig}
                r["label"] = new
                n_change += 1
        print(f"{split}: {len(rows):,} rows, relabel {n_change}")
        if apply and n_change:
            shutil.copy(path, path + ".bak_v1")
            with open(path, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["text", "label", "source"])
                w.writeheader()
                w.writerows(rows)
            print(f"  applied (backup: {path}.bak_v1)")
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(changes, f, ensure_ascii=False, indent=1)
    print(f"changes: {len(changes)} → {OUT_JSON}")


if __name__ == "__main__":
    main()
