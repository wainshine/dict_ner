#!/usr/bin/env python3
"""UNKNOWN 合成增广 — 生成 5 万条负样本 → data/v3_synth_unknown.csv

类别: 随机英文/数字/单字/乱序汉字/符号汤/英数混合/括号模式
用法: python v3/synth_unknown.py [--n 50000]
"""
import argparse
import csv
import os
import random
import string
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "v3_synth_unknown.csv")

COMMON_CHARS = "的一是不了人我在有他这中大来上国个到说们为子和你地出道也时年得就那都要下以生会自着去之过家学对可她里后小么心多天而能好都然没日于起还发成事只作当想看文无开手十用主行方又如前所本见经头面公同三已老从动两长知民样现分将外但身些与高意进法此月正儿世点被由名度相果今其全工间何或者北平次于把向想边每门金别四安员五更关己内第位石风回龙布名西飞和六书机再军水您家白包元七走八议且因什斯许区东团员新交"

LATIN_WORDS = ["hello", "world", "test", "abc", "xyz", "foo", "bar", "python",
               "github", "docker", "linux", "apple", "google", "amazon", "wifi",
               "email", "http", "https", "www", "com", "net", "org", "app"]


def gen_latin(rng):
    if rng.random() < 0.5:
        w = rng.choice(LATIN_WORDS)
        return w + (str(rng.randint(0, 9999)) if rng.random() < 0.4 else "")
    n = rng.randint(2, 12)
    return "".join(rng.choice(string.ascii_letters) for _ in range(n))


def gen_digits(rng):
    n = rng.randint(1, 11)
    return "".join(rng.choice(string.digits) for _ in range(n))


def gen_single_char(rng):
    return rng.choice(COMMON_CHARS)


def gen_jumble(rng):
    n = rng.randint(2, 6)
    return "".join(rng.choice(COMMON_CHARS) for _ in range(n))


def gen_symbols(rng):
    syms = "!@#$%^&*()[]{}<>~`_-+=|\\:;\"',./?！？…—【】、。·"
    n = rng.randint(1, 6)
    return "".join(rng.choice(syms) for _ in range(n))


def gen_mixed(rng):
    n = rng.randint(3, 8)
    chars = string.ascii_lowercase + string.digits
    return "".join(rng.choice(chars) for _ in range(n))


def gen_paren(rng):
    pats = ["({})", "[{}]", "<{}>", "【{}】", "{}()", "{}..."]
    inner = rng.choice([gen_latin(rng), gen_digits(rng), gen_jumble(rng)])
    return rng.choice(pats).format(inner)


GENS = [gen_latin, gen_digits, gen_single_char, gen_jumble,
        gen_symbols, gen_mixed, gen_paren]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    seen = set()
    rows = []
    while len(rows) < args.n:
        g = rng.choice(GENS)
        t = g(rng).strip()
        if not t or t in seen or len(t) > 50:
            continue
        seen.add(t)
        rows.append((t, "UNKNOWN", "synth", ""))

    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["text", "label", "source", "type_orig"])
        w.writerows(rows)
    print(f"generated {len(rows):,} -> {args.out}")


if __name__ == "__main__":
    main()
