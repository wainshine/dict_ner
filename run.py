#!/usr/bin/env python3
"""dict_ner v1.2.3 — 中文地名/机构名/POI/品牌识别系统 CLI"""
import os, sys, json
import logging
logging.basicConfig(level=logging.INFO, format="%(message)s")

VERSION = "v1.2.3"
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from pipeline import DictNerPipeline


def cmd_recognize(text: str):
    pipe = DictNerPipeline()
    print(pipe.recognize_simple(text))


def cmd_json(text: str):
    pipe = DictNerPipeline()
    print(json.dumps(pipe.recognize(text), ensure_ascii=False, indent=2))


def cmd_info():
    pipe = DictNerPipeline()
    print(f"dict_ner {VERSION}")
    print(f"  地名:   dicts/{pipe.loc_version}.pkl")
    print(f"  机构:   dicts/org_{pipe.org_version}.pkl")
    print(f"  POI:    dicts/{pipe.poi_version}.pkl")
    print(f"  品牌:   dicts/brand_{pipe.org_version}.pkl")
    print()
    print(f"使用: python run.py recognize \"深圳市南山区华为技术有限公司\"")
    print(f"      python run.py json \"北京市朝阳区星巴克咖啡\"")
    print(f"      python run.py info")


def main():
    c = sys.argv[1] if len(sys.argv) > 1 else "info"
    if c == "info":
        cmd_info()
    elif c in ("rec", "recognize"):
        text = sys.argv[2] if len(sys.argv) > 2 else input("输入文本: ")
        cmd_recognize(text)
    elif c == "json":
        text = sys.argv[2] if len(sys.argv) > 2 else input("输入文本: ")
        cmd_json(text)
    elif c in ("test", "t"):
        tests = [
            "深圳市南山区华为技术有限公司",
            "北京市朝阳区星巴克咖啡国贸店",
            "阿里巴巴网络技术有限公司",
            "陕西省安康市旬阳县XX公司",
            "峨眉山景区游客中心",
            "中国工商银行股份有限公司北京分行",
        ]
        pipe = DictNerPipeline()
        for t in tests:
            print(pipe.recognize_simple(t))
            print()
    else:
        print(f"未知命令: {c}")
        cmd_info()


if __name__ == "__main__":
    main()
