#!/usr/bin/env python3
"""Build eval set from Gaode/Tencent raw data + manual cases → eval_set.csv"""
import csv
import os
import random
import sys

csv.field_size_limit(sys.maxsize)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import DATA_DIR

random.seed(42)

GAODE_DIR = os.path.join(DATA_DIR, "高德amap")
TENCENT_DIR = os.path.join(DATA_DIR, "腾讯地图")
OUT_PATH = os.path.join(DATA_DIR, "eval_set.csv")

GAODE_TYPE_MAP = {
    "政府机构及社会团体": "ORG",
    "金融保险服务": "ORG",
    "公司企业": "ORG",
    "科教文化服务": "ORG",
    "医疗保健服务": "ORG",
    "住宿服务": "POI",
    "餐饮服务": "POI",
    "购物服务": "POI",
    "生活服务": "POI",
    "汽车维修": "POI",
    "汽车服务": "POI",
    "汽车销售": "POI",
    "摩托车服务": "POI",
    "旅游服务": "POI",
    "体育休闲服务": "POI",
    "交通设施服务": "POI",
    "通行设施": "POI",
    "公共设施": "POI",
    "道路附属设施": "POI",
    "商务住宅": "ADDR",
    "地名地址信息": "ADDR",
    "风景名胜": "ADDR",
}

GAODE_SKIP_TYPES = {"事件活动", "室内设施"}

TENCENT_TYPE_MAP = {
    "公司企业": "ORG",
    "银行金融": "ORG",
    "机构团体": "ORG",
    "教育学校": "ORG",
    "医疗保健": "ORG",
    "文化场馆": "ORG",
    "酒店宾馆": "POI",
    "购物": "POI",
    "美食": "POI",
    "生活服务": "POI",
    "旅游服务": "POI",
    "运动健身": "POI",
    "基础设施": "POI",
    "交通运输": "POI",
    "汽车": "POI",
    "建筑房产": "ADDR",
    "地名地址": "ADDR",
    "休闲娱乐": "ADDR",
}

TENCENT_SKIP_TYPES = {"其它", "公交线编号"}

MANUAL_CASES = [
    # ADDR 60
    ("北京市朝阳区", "ADDR"), ("上海市浦东新区", "ADDR"), ("深圳市南山区", "ADDR"),
    ("广东省广州市", "ADDR"), ("浙江省杭州市", "ADDR"), ("四川省成都市", "ADDR"),
    ("武汉市洪山区", "ADDR"), ("南京市鼓楼区", "ADDR"), ("西安市雁塔区", "ADDR"),
    ("长沙市岳麓区", "ADDR"), ("天津市和平区", "ADDR"), ("重庆市渝中区", "ADDR"),
    ("青岛市市南区", "ADDR"), ("大连市中山区", "ADDR"), ("厦门市思明区", "ADDR"),
    ("郑州市金水区", "ADDR"), ("济南市历下区", "ADDR"), ("合肥市蜀山区", "ADDR"),
    ("福州市鼓楼区", "ADDR"), ("南宁市青秀区", "ADDR"),
    ("西湖", "ADDR"), ("太湖", "ADDR"), ("泰山", "ADDR"), ("长江", "ADDR"),
    ("黄河", "ADDR"), ("峨眉山", "ADDR"), ("洞庭湖", "ADDR"), ("鄱阳湖", "ADDR"),
    ("北戴河", "ADDR"), ("黄山", "ADDR"), ("华山", "ADDR"), ("衡山", "ADDR"),
    ("嵩山", "ADDR"), ("九寨沟", "ADDR"), ("张家界", "ADDR"),
    ("深南大道", "ADDR"), ("长安街", "ADDR"), ("南京路", "ADDR"),
    ("中山路", "ADDR"), ("解放路", "ADDR"), ("建设路", "ADDR"),
    ("人民路", "ADDR"), ("和平路", "ADDR"), ("五四路", "ADDR"), ("东风路", "ADDR"),
    ("人民路88号", "ADDR"), ("中山路100号", "ADDR"), ("解放路66号", "ADDR"),
    ("建设路18号", "ADDR"), ("南京东路299号", "ADDR"),
    ("北京市朝阳区建国路88号", "ADDR"), ("上海市浦东新区陆家嘴环路1000号", "ADDR"),
    ("深圳市南山区科技园南一道", "ADDR"), ("杭州市西湖区北山街8号", "ADDR"),
    ("广东省广州市天河区体育西路101号", "ADDR"),

    # ORG 50
    ("华为技术有限公司", "ORG"), ("阿里巴巴网络技术有限公司", "ORG"),
    ("腾讯科技(深圳)有限公司", "ORG"), ("百度在线网络技术有限公司", "ORG"),
    ("字节跳动有限公司", "ORG"), ("京东集团股份有限公司", "ORG"),
    ("小米科技有限责任公司", "ORG"), ("比亚迪股份有限公司", "ORG"),
    ("中国平安保险(集团)股份有限公司", "ORG"), ("宁德时代新能源科技股份有限公司", "ORG"),
    ("广东省卫健委", "ORG"), ("北京市卫生健康委员会", "ORG"),
    ("深圳市市场监督管理局", "ORG"), ("杭州市西湖区街道办事处", "ORG"),
    ("武汉市卫生健康局", "ORG"), ("南京市公安局", "ORG"),
    ("西安市财政局", "ORG"), ("成都市规划局", "ORG"),
    ("厦门市事务局", "ORG"), ("郑州市教育局", "ORG"),
    ("北京协和医院", "ORG"), ("四川大学华西医院", "ORG"),
    ("中国人民解放军总医院", "ORG"), ("复旦大学附属中山医院", "ORG"),
    ("北京大学第一医院", "ORG"), ("上海交通大学医学院附属瑞金医院", "ORG"),
    ("深圳市人民医院", "ORG"), ("广东省人民医院", "ORG"),
    ("南京市鼓楼医院", "ORG"), ("武汉市同济医院", "ORG"),
    ("清华大学", "ORG"), ("北京大学", "ORG"), ("浙江大学", "ORG"),
    ("复旦大学", "ORG"), ("上海交通大学", "ORG"), ("武汉大学", "ORG"),
    ("中山大学", "ORG"), ("中国人民大学附属中学", "ORG"),
    ("上海中学", "ORG"), ("北京市第四中学", "ORG"),
    ("中国工商银行股份有限公司", "ORG"), ("中国建设银行股份有限公司", "ORG"),
    ("中国农业银行股份有限公司", "ORG"), ("中国银行股份有限公司", "ORG"),
    ("招商银行股份有限公司", "ORG"), ("交通银行股份有限公司", "ORG"),
    ("中信银行股份有限公司", "ORG"), ("中国民生银行股份有限公司", "ORG"),
    ("兴业银行股份有限公司", "ORG"), ("上海浦东发展银行股份有限公司", "ORG"),

    # POI 40
    ("星巴克咖啡望京店", "POI"), ("肯德基黄河路店", "POI"),
    ("麦当劳天河广场店", "POI"), ("海底捞火锅三里屯店", "POI"),
    ("喜茶海岸城店", "POI"), ("瑞幸咖啡中关村店", "POI"),
    ("必胜客陆家嘴店", "POI"), ("德克士春熙路店", "POI"),
    ("全季酒店南京路店", "POI"), ("如家快捷酒店火车站店", "POI"),
    ("XX火锅店", "POI"), ("XX烧烤店", "POI"), ("XX面馆", "POI"),
    ("XX海鲜城", "POI"), ("XX奶茶店", "POI"),
    ("XX停车场", "POI"), ("公共厕所", "POI"), ("XX加油站", "POI"),
    ("XX收费站", "POI"), ("XX公交站", "POI"), ("XX地铁站", "POI"),
    ("XX汽车站", "POI"), ("XX火车站", "POI"), ("XX轮渡码头", "POI"),
    ("XX超市", "POI"), ("XX便利店", "POI"), ("XX商场", "POI"),
    ("XX菜市场", "POI"), ("XX批发市场", "POI"),
    ("XX大酒店", "POI"), ("XX商务酒店", "POI"), ("XX宾馆", "POI"),
    ("XX旅馆", "POI"), ("XX招待所", "POI"), ("汉庭酒店北京西站店", "POI"),
    ("7天连锁酒店深圳北站店", "POI"), ("维也纳酒店成都春熙路店", "POI"),
    ("锦江之星上海外滩店", "POI"), ("莫泰168连锁酒店杭州西湖店", "POI"),

    # UNKNOWN 50
    ("Hello World", "UNKNOWN"), ("Good Morning", "UNKNOWN"),
    ("test123", "UNKNOWN"), ("abc123", "UNKNOWN"),
    ("pytorch", "UNKNOWN"), ("transformer", "UNKNOWN"),
    ("github", "UNKNOWN"), ("chatgpt", "UNKNOWN"),
    ("opencode", "UNKNOWN"), ("vscode", "UNKNOWN"),
    ("12345", "UNKNOWN"), ("67890", "UNKNOWN"), ("99999", "UNKNOWN"),
    ("1234567890", "UNKNOWN"), ("00001", "UNKNOWN"),
    ("31415926", "UNKNOWN"), ("27182818", "UNKNOWN"),
    ("20240701", "UNKNOWN"), ("1", "UNKNOWN"), ("01", "UNKNOWN"),
    ("", "UNKNOWN"), ("啊", "UNKNOWN"), ("的", "UNKNOWN"),
    ("了", "UNKNOWN"), ("吗", "UNKNOWN"), ("呢", "UNKNOWN"),
    ("吧", "UNKNOWN"), ("嗯", "UNKNOWN"), ("好", "UNKNOWN"),
    ("哦", "UNKNOWN"),
    ("!@#$%", "UNKNOWN"), ("***", "UNKNOWN"), ("...", "UNKNOWN"),
    ("()[]", "UNKNOWN"), ("<tag>", "UNKNOWN"), ("{json}", "UNKNOWN"),
    ("&nbsp;", "UNKNOWN"), ("\n\t", "UNKNOWN"),
    ("1234abcd", "UNKNOWN"), ("##heading", "UNKNOWN"),
    ("的了吧吗", "UNKNOWN"), ("是的是什么", "UNKNOWN"),
    ("个和可以", "UNKNOWN"), ("不在有", "UNKNOWN"),
    ("我你他她", "UNKNOWN"), ("这那什么", "UNKNOWN"),
    ("因为所以", "UNKNOWN"), ("虽然但是", "UNKNOWN"),
    ("如果那么", "UNKNOWN"), ("而且或者", "UNKNOWN"),
]


def _safe_text(text):
    if not text:
        return None
    text = text.strip()
    if not text or len(text) > 50:
        return None
    if text.isdigit():
        return None
    return text


def _reservoir_sample(iterator, k):
    result = []
    for i, item in enumerate(iterator):
        if i < k:
            result.append(item)
        else:
            j = random.randint(0, i)
            if j < k:
                result[j] = item
    return result


def sample_gaode():
    files = sorted([f for f in os.listdir(GAODE_DIR) if f.endswith(".csv")])

    # Pass 1: count type distribution across all files
    type_counts = {}
    total_valid = 0
    for fname in files:
        path = os.path.join(GAODE_DIR, fname)
        if os.path.getsize(path) == 0:
            continue
        with open(path, encoding="gbk", errors="replace") as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                if len(row) < 10:
                    continue
                name = (row[6] or "").strip()
                typ = (row[9] or "").strip()
                if not name:
                    continue
                t1 = typ.split(";")[0] if typ else ""
                if not t1 or t1 in GAODE_SKIP_TYPES:
                    continue
                if GAODE_TYPE_MAP.get(t1) is None:
                    continue
                if "自动提款机" in typ or "自助银行" in typ:
                    continue
                type_counts[t1] = type_counts.get(t1, 0) + 1
                total_valid += 1

    target_total = 100000
    type_targets = {t: max(50, round(target_total * c / total_valid)) for t, c in type_counts.items()}
    print(f"Gaode pass1: {total_valid:,} valid rows, type targets:")

    # Pass 2: reservoir sample by type
    samples_by_type = {t: [] for t in type_targets}
    seen_by_type = {t: 0 for t in type_targets}
    for fname in files:
        path = os.path.join(GAODE_DIR, fname)
        if os.path.getsize(path) == 0:
            continue
        with open(path, encoding="gbk", errors="replace") as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                if len(row) < 10:
                    continue
                text = _safe_text(row[6])
                if not text:
                    continue
                typ = (row[9] or "").strip()
                t1 = typ.split(";")[0] if typ else ""
                if not t1 or t1 in GAODE_SKIP_TYPES:
                    continue
                label = GAODE_TYPE_MAP.get(t1)
                if label is None:
                    continue
                if "自动提款机" in typ or "自助银行" in typ:
                    continue
                target = type_targets.get(t1, 0)
                buf = samples_by_type.get(t1)
                if buf is None:
                    continue
                item = (text, label, "gaode", t1)
                seen = seen_by_type[t1]
                if seen < target:
                    buf.append(item)
                else:
                    j = random.randint(0, seen)
                    if j < target:
                        buf[j] = item
                seen_by_type[t1] = seen + 1

    # Collect natural place names
    natural = []
    for fname in files:
        path = os.path.join(GAODE_DIR, fname)
        if os.path.getsize(path) == 0:
            continue
        with open(path, encoding="gbk", errors="replace") as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                if len(row) < 10:
                    continue
                text = _safe_text(row[6])
                if not text:
                    continue
                typ = (row[9] or "").strip()
                parts = [p for p in typ.split(";") if p]
                if len(parts) >= 3 and parts[0] == "地名地址信息" and parts[1] == "自然地名":
                    natural.append((text, "ADDR", "gaode_natural", parts[2] if len(parts) > 2 else "自然地名"))
                    if len(natural) >= 30000:
                        break
        if len(natural) >= 30000:
            break

    results = []
    for t, samples in sorted(samples_by_type.items()):
        results.extend(samples)
        actual = len(samples)
        print(f"  {t:<20s}: target={type_targets.get(t,0):>6,} actual={actual:>6,}")

    results.extend(natural)
    print(f"Gaode: {len(results):,} samples ({len(natural):,} natural) from {len(files)} files")
    return results


def sample_tencent():
    files = [f for f in os.listdir(TENCENT_DIR) if f.endswith(".csv")]
    total_size = sum(os.path.getsize(os.path.join(TENCENT_DIR, f)) for f in files)
    if total_size == 0:
        return []

    target_total = 50000
    results = []

    for fname in files:
        path = os.path.join(TENCENT_DIR, fname)
        size = os.path.getsize(path)
        target = max(50, round(target_total * size / total_size))
        samples = []
        with open(path, encoding="gbk", errors="replace") as f:
            reader = csv.reader(f)
            rows = []
            for row in reader:
                if len(row) < 7:
                    continue
                text = _safe_text(row[1])
                if not text:
                    continue
                cat_raw = (row[6] or "").strip()
                cat_1st = cat_raw.split(";")[0] if cat_raw else ""
                if not cat_1st or cat_1st in TENCENT_SKIP_TYPES:
                    continue
                label = TENCENT_TYPE_MAP.get(cat_1st)
                if label is None:
                    continue
                samples.append((text, label, "tencent", cat_1st))

        results.extend(_reservoir_sample(samples, target))

    print(f"Tencent: {len(results):,} samples from {len(files)} files")
    return results


def build():
    results = []
    results.extend(sample_gaode())
    results.extend(sample_tencent())
    for text, label in MANUAL_CASES:
        results.append((text, label, "manual", ""))

    random.shuffle(results)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["text", "label", "source", "type_orig"])
        writer.writerows(results)

    print(f"\nTotal: {len(results):,} entries → {OUT_PATH}")
    labels = {}
    for _, label, _, _ in results:
        labels[label] = labels.get(label, 0) + 1
    for lb in ("ORG", "POI", "ADDR", "UNKNOWN"):
        print(f"  {lb}: {labels.get(lb, 0):,}")


if __name__ == "__main__":
    build()
