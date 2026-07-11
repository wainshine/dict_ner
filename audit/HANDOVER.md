# HANDOVER.md v2.2.1

> 最后更新: 2026-07-11
> v2.2.1: 段类型体系修复 + 复合机构检测 + 过度拆分合并 + VILLAGE 清理
> 详见 `audit/` 目录下 8 份审计/方案报告

## 项目概况

从非结构化中文文本识别地名/机构名/POI/品牌名，四个模组共用 Viterbi DP 引擎。

v2.2.1 新增 SegType.ORG_SUFFIX 枚举，ORG 和 POI 段类型输出层分离。pipeline 层新增复合机构检测（非末段"有限公司"→切分重识别）和过度拆分合并（相邻段合并后查 SQL CSV 校验）。LOC 词典 VILLAGE 清理（依据 areas/ 五级行政区划）。

- 总代码量: ~3800 行 Python, 词典 ~45MB, 数据 ~16GB
- 测试覆盖: **112 条用例**, `python3 -m unittest discover -v -s tests/`
- Python 3.10+, 纯标准库

## 关键文件

### 生产代码

```
pipeline.py          → DictNerPipeline 统一总线 + classify()
run.py               → CLI 入口
core/config.py       → 共享常量 (VERSION=v1.2.3, NUM_CHUNKS, 路径)
core/types.py        → SegType 枚举 + ADMIN_SUFFIX_MAP + POI_SUFFIX_MAP
core/csv_index.py    → 三SQL CSV 亲和度运行时索引
core/suffix_matcher.py → 后缀边界合并
loc/                 → 地名: builder.py + recognizer.py + importer.py
org/                 → 机构名: recognizer.py (456行, ORG DP核心)
poi/                 → POI: recognizer.py (19行, thin wrapper)
brand/               → 品牌: model.py (bigram概率)
```

### 训练工具

```
tools/pipeline_base.py       → 共享函数
tools/org_launch.py          → org 全量训练 (16并行, ~6min)
tools/org_aggregate.py       → org 聚合+剪枝+gov seed注入+POI排除
tools/poi_launch.py          → poi 全量训练 (16并行, ~4min)
tools/poi_aggregate.py       → poi 聚合+剪枝+POI override注入
tools/poi_dedup.py           → A+T 去重
tools/merge_gaode_roads.py   → Gaode道路名合并入LOC词典
tools/build_eval_set.py      → 评测集构建 (18万条, 按type比例采样+自然地名)
tools/eval_classify.py       → 分类评测
```

### 数据扫描脚本

```
scripts/build_gaode_index.py → 单次扫描Gaode 67文件 → d4_category_map.pkl + suffix_category_gaode.csv + gaode_roads.csv
scripts/validate_d4_map.py   → d4_category_map vs SQL CSV 一致性校验
```

### 数据文件

| 文件 | 大小 | 说明 |
|------|------|------|
| `data/split/{loc,org,poi}/` | 10GB | 16chunk分片, 训练直接读取 |
| `data/高德amap/` | 11GB | 67文件, GBK, 6450万行 |
| `data/腾讯地图/` | 7.5GB | 345文件, GBK, 7200万行 |
| `data/addr_segments_sql.csv` | 81MB | SQL切分的地址段 (d1) |
| `data/trade_segments_sql.csv` | 1.6MB | SQL切分的行业段 (d3) |
| `data/suffix_segments_sql.csv` | 982KB | SQL切分的后缀段 (d4) |
| `data/gov_suffix_seed.csv` | 29条 | 政府后缀种子 (Gaode验证) |
| `data/gaode_roads.csv` | 7MB | 47万Gaode道路名 (freq≥5, 已拆分复合名) |
| `data/eval_set.csv` | 7MB | 18万条评测集 (按type比例采样) |
| `dicts/*v1.2.3.pkl` | 45MB | 当前词典 (4个) |
| `dicts/*v1.2.0.pkl` | 45MB | 上一版词典 (4个) |
| `dicts/*v1.1.2.pkl` | 38MB | 兜底词典 (4个) |
| `dicts/*v1.1.1.pkl` | 38MB | 兜底词典 (4个, **不可删**) |
| `dicts/d4_category_map.pkl` | 0.2MB | 9,577条d4 Gaode标注 |
| `dicts/suffix_category_gaode.csv` | ~40KB | 1,520条高置信后缀 |
| `dicts/iter_v1.2.3/` | ~1.5GB | ORG/POI 统计中间产物 |

## SQL遗存对应表

| SQL旧名 | 新名 | 含义 |
|---------|------|------|
| d1 / d111 | addr_seg | 行政区划段 |
| d2 / d222 | brand_seg | 品牌/专名段 |
| d3 / d333 | trade_seg | 行业属性段 |
| d4 / d444 | suffix_seg | 后缀段 |

## classify() 判定链

```
规则1: 公司/政府后缀在末位 → ORG
规则2: d4 不在 SQL CSV 后缀表中 → 非标准后缀(地址+店) → POI
规则3: d4 精确查 d4_category_map → POI_FAC/POI_STORE/ORG
规则4: d4 endswith 查 suffix_category_gaode → POI_FAC/POI_STORE/ORG
规则5: argmax (geo_cov驱动addr_score, T_UNKNOWN=0.10兜底)
```

### classify 评测 (18万条)

| 指标 | v2.2.1 | baseline v1.2.3 | Delta |
|------|:---:|:---:|:---:|
| macro-F1 | 0.3702 | 0.3513 | +0.0189 |
| ORG F1 | 0.5203 | 0.3925 | +0.1278 |
| POI F1 | 0.5419 | 0.6599 | -0.1180 |
| ADDR F1 | 0.4163 | 0.3529 | +0.0634 |

## 从零重建

### 数据扫描 (~30min, 一次性)

```bash
python scripts/build_gaode_index.py
# 产出: d4_category_map.pkl + suffix_category_gaode.csv + gaode_roads.csv
```

### 地名词典 (~6min)

```bash
python -c "
from loc.builder import DictBuilder
b = DictBuilder('dicts', 'loc_v1.2.3')
b.build_from_loc36kw('data'); b.build_from_areas('data')
b.build_from_d444('data'); b.cleanup()
b.build_orientation_dict(); b.build_location_dict(); b.save()
"
python tools/merge_gaode_roads.py   # 合并47万Gaode道路名
```

### 机构名 (~6min, 16并行)

```bash
python tools/org_launch.py split stats
python tools/org_aggregate.py
```

### 品牌模型 (~1min)

```bash
python -c "
from brand.model import BrandModel
m = BrandModel('dicts', version='v1.2.3')
m.train_from_d2_csv('dicts/iter_iter_v1.2.3/org_d2_freqs_v1.2.1.csv', min_freq=3, min_bigram_count=10)
m.save()
"
```

### POI (~4min, 16并行)

```bash
python tools/poi_dedup.py
python tools/poi_launch.py split stats
python tools/poi_aggregate.py
```

### 评测

```bash
python tools/build_eval_set.py                                    # 18万评测集
python tools/eval_classify.py --eval data/eval_set.csv            # 跑评测
python tools/eval_classify.py --eval data/eval_set.csv --baseline baseline.json  # 对比
python scripts/validate_d4_map.py                                 # SQL CSV校验
```

## v2.1.0 重构摘要

| 问题 | 方案 | 效果 |
|------|------|------|
| **手工后缀列表维护难** | `d4_category_map.pkl` (9,577条Gaode标注) + `suffix_category_gaode.csv` (1,520条) 替代手写 ~80条 | 数据驱动, 可自动更新 |
| **suffix CSV 无法区分ORG/POI** | Gaode type标注补充商业分类维度 | ~5,000条d4获得POI/ORG标注 |
| **d4∉SQL CSV → 误判** | 规则: 非标准后缀(地址+店名) → POI | POI→UNKNOWN 修复84%, POI→ADDR 修复81% |
| **LOC 道路名缺失** | `merge_gaode_roads.py` 从Gaode address提取47万道路名注入LOC词典 | ROAD词条 150K → 524K |
| **gov seed 不足** | Gaode验证扩充至29条 (派出所/村委会/警务室等) | 政府机构识别改善 |
| **eval_set 采样偏差** | 按全量type比例采样+自然地名全量注入+ATM过滤 | 18万条代表性评测集 |

## v2.0.0 → v2.1.0 关键区别

| 维度 | v2.0.0 | v2.1.0 |
|------|------|------|
| 后缀判定 | 3个手工set (~80条) | d4_category_map (9,577条) + suffix_table (1,520条) |
| LOC道路名 | 150K (loc builder) | 524K (+374K from Gaode) |
| gov seed | 19条 | 29条 (Gaode验证) |
| d4不在SQL CSV | 未处理 | 判定为POI |
| eval_set | 15万 (按文件均分) | 18万 (按type比例+自然地名) |
| 词典版本 | v1.2.2 | v1.2.3 |
| 测试数 | 108 | 112 |

## 踩过的坑

1. **multiprocessing + spawn**: macOS Python 3.14 默认 spawn, 必须独立 .py + `__name__` 包裹。最稳方案: bash `&` 16进程
2. **d444 temp字段**: 不是质量分, 是处理阶段标记
3. **suffix_segments_sql.csv 无法区分ORG/POI**: org_ratio 衡量语料频率而非实体类型, 需Gaode补充商业分类维度
4. **d4∉SQL CSV → POI**: "XX黄河路店"中"店"不在SQL CSV → 地址信息嵌入名称 → 一定POI
5. **道路名复合名**: Gaode address中"药王路与香山路"需拆分处理
6. **单字符后缀缺失**: "店""馆"不在SQL CSV (d4≥2), 但实际是高频后缀, 需手动补入suffix_table
7. **csv.field_size_limit**: 3个Gaode文件超默认限制, 需设100MB
8. **Gaode单文件type分布偏移**: 不能按文件均分采样, 需先扫描全量type分布再按比例采样
9. **体系循环**: loc/org/poi 各自跑全量统计、各自剪枝, 互不混用
10. **POI dict_name**: poi_chunk_stats.py 必须传 dict_name 而非 version, 否则加载org词典

## 当前状态

- 系统版本: **v2.2.1**, 词典: **v1.2.3** (当前) v1.2.0 v1.2.1 v1.2.2 + v1.1.2 + v1.1.1 (兜底, **不可删**)
- 测试: **112 用例** 全部通过
- 评测: 18万条, macro-F1 0.3706 (超基线 +0.0193)
- 审计: 七代全部闭环 (v1.0 50/50 + 二代 N1-N24 + 三代 F1-F22 + 四代 Finding 1-19 + v2.0.0 + v2.1.0)
