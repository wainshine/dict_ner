#!/usr/bin/env python3
"""提取低频序列 badcase → CSV"""
import argparse, json, os, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval", required=True, choices=["org", "poi", "loc"])
    parser.add_argument("--max-freq", type=int, default=10)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()

    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "output", f"{args.eval}_eval", f"{args.eval}_{args.version}")
    if not os.path.isdir(base_dir):
        print(f"Not found: {base_dir}")
        return

    all_seqs = Counter()
    for fname in sorted(os.listdir(base_dir)):
        if not fname.endswith(".jsonl"):
            continue
        spath = os.path.join(base_dir, fname.replace(".jsonl", "_stats.json"))
        if os.path.exists(spath):
            with open(spath) as f:
                s = json.load(f)
            all_seqs += Counter(s.get("seq_dist", {}))

    low_seqs = {k for k, v in all_seqs.items() if v < args.max_freq}
    print(f"Total seqs: {len(all_seqs):,}, low-freq (<{args.max_freq}): {len(low_seqs):,}")

    out_rows = []
    for fname in sorted(os.listdir(base_dir)):
        if not fname.endswith(".jsonl"):
            continue
        jpath = os.path.join(base_dir, fname)
        with open(jpath, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                seq = " → ".join(s["type"] for s in r["segments"])
                if seq in low_seqs:
                    out_rows.append((r["original"], seq, all_seqs.get(seq, 0)))

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    out_path = os.path.join(out_dir, f"badcase_{args.eval}_{args.version}.csv")
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        f.write("text,seq,freq\n")
        for text, seq, freq in out_rows:
            text_escaped = text.replace('"', '""')
            f.write(f'"{text_escaped}",{seq},{freq}\n')

    print(f"Badcase: {len(out_rows):,} records → {out_path}")


if __name__ == "__main__":
    main()
