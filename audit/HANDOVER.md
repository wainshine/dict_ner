# HANDOVER.md v1.2.2

> 最后更新: 2026-07-06
> 审计状态: 4 项架构级问题 (H1-H4) 已修复, 代码净减 248 行
> 详见 `audit/` 目录下审计报告

## 项目概况

`dict_ner` 是一个从非结构化中文文本中识别地名/机构名/POI/品牌名的系统，四个模组基于同一 Viterbi DP 引擎，各有独立词典。

- 总代码量: ~3200行 Python
- 词典总大小: ~40MB
- 全量数据: ~18GB (含分片)
- 识别速度: ~15K rec/s (单核)

## 已完成模块

| 模块 | 算法 | 词典 (v1.1.2) | 数据 | 状态 |
|------|------|------|------|:--:|
| loc (地名) | Viterbi DP | 120万 (loc3.6kw idf + areas) | loc3.6kw 3635万 | ✅ |
| org (机构名) | Viterbi DP | d1=64K d3=20K d4=9.6K | org16kw 1.65亿 | ✅ |
| poi (POI) | 复用org DP | d1=44K d3=4.8K d4=16K | 兴趣点A+T 1.37亿→去重4000万 | ✅ |
| brand (品牌) | 字级bigram | 90万 bigram, 分离度4.1 | org d2段 427万条 | ✅ |

## 四模组调用链

```
pipeline.py → DictNerPipeline.recognize(text)
  ├── loc.recognize(text)      → 地名段
  ├── org.recognize(text)      → 机构名段
  ├── poi.recognize(text)      → POI段 (如果机构结果不含公司后缀)
  └── brand.brand_score(word)  → 品牌概率 (org DP内部调用)
```

## 识别质量

| | 地名 | 机构名 | POI | 品牌 |
|--|:--:|:--:|:--:|:--:|
| 采样量 | 5000 | 20000 | 20000 | — |
| OK率 | — | 93.3% | — | — |
| Score (loc) | 62.6 | — | — | — |
| d2_as_d4 badcase | — | 3.6% | 0 | — |
| d4覆盖命中 | — | 103% | 113% | — |
| 分离度 | — | — | — | 4.1 |

"华为" brand_score: 0.0006, "字节跳动": 0.0227, "有限公司": 0.0008

## 关键文件

### 生产代码

```
pipeline.py          → DictNerPipeline 统一总线
run.py               → CLI 入口
core/config.py       → 共享常量 (VERSION, NUM_CHUNKS, ADDR_TYPES, 路径)
core/types.py        → SegType 枚举 + ADMIN_SUFFIX_MAP + POI_SUFFIX_MAP (从CSV加载)
core/suffix_matcher.py → 后缀边界合并 (loc/importer + loc/recognizer 共用)
loc/                 → 地名: builder.py (构建) + recognizer.py (识别) + importer.py
org/                 → 机构名: recognizer.py (核心, 456行)
poi/                 → POI: recognizer.py (thin wrapper over org DP)
brand/               → 品牌: model.py (bigram概率)
```

### 训练/迭代工具

```
tools/pipeline_base.py    → 共享函数: count_lines, split_file, launch_parallel, aggregate_stats_files, export_d2_csv
tools/org_launch.py       → org 全量: split→clean→stats (16并行, ~6min)
tools/org_chunk_stats.py   → org per-chunk DP统计
tools/org_aggregate.py     → org 聚合+剪枝 (d1≥5, d3≥3, d4≥100)

tools/poi_launch.py        → poi 全量: dedup→split→clean→stats (~4min)
tools/poi_chunk_stats.py    → poi per-chunk DP统计 (注意: 必须传dict_name)
tools/poi_aggregate.py      → poi 聚合+剪枝 (d1≥5, d3≥10, d4≥100 + seed)
tools/poi_dedup.py          → poi A+T去重+词频 (仅全量重建时需要)
```

### 数据文件

| 文件 | 大小 | 说明 |
|------|------|------|
| `data/split/{loc,org,poi}/` | 10GB | 16chunk分片 (训练直接读取) |
| `data/areas/` | 36MB | 五级行政区划 |
| `data/addr_segments_sql.csv` | 81MB | SQL切分的地址段 (d111) |
| `data/trade_segments_sql.csv` | 1.6MB | SQL切分的行业段 (d333) |
| `data/suffix_segments_sql.csv` | 982KB | SQL切分的后缀段 (d444) |
| `data/suffix_seed.csv` | 429KB | POI后缀种子 (从d444提取) |
| `dicts/poi_suffix_category.csv` | 131行 | 后缀→类别映射 (统一数据源) |

## SQL遗存对应表

| SQL旧名 | 新名 | 含义 |
|---------|------|------|
| d1 / d111 | addr_seg / addr_segments_sql.csv | 行政区划段 |
| d2 / d222 | brand_seg / brand_segments_sql.csv | 品牌/专名段 |
| d3 / d333 | trade_seg / trade_segments_sql.csv | 行业属性段 |
| d4 / d444 | suffix_seg / suffix_segments_sql.csv | 后缀段 |

## 如何从零重建

```bash
# 1. 地名词典 (~4min)
python -c "
from loc.builder import DictBuilder
b = DictBuilder('dicts', 'loc_v1.1.2')
b.build_from_loc36kw('data'); b.build_from_areas('data')
b.build_from_d444('data'); b.cleanup()
b.build_orientation_dict(); b.build_location_dict(); b.save()
"

# 2. 机构名词典 (~6min, 16并行)
python tools/org_launch.py split stats
python tools/org_aggregate.py

# 3. 品牌模型 (~1min)
python -c "
from brand.model import BrandModel
m = BrandModel('dicts', version='v1.1.2')
m.train_from_d2_csv('dicts/iter_v1.1.2/org_d2_freqs_v1.1.2.csv', min_freq=3, min_bigram_count=10)
m.save()
"

# 4. POI词典 (~4min, 16并行)
python tools/poi_dedup.py
python tools/poi_launch.py split stats
python tools/poi_aggregate.py
```

## v1.2.2 重构摘要 (2026-07-06)

基于审计报告 `audit/00_审计概要_v1.0.md` 完成四项架构级修复:

| 问题 | 方案 | 效果 |
|------|------|------|
| **H1**: org/poi 工具链 ~80% 重复 | `core/config.py` + `tools/pipeline_base.py` | 6个文件净减 248 行 |
| **H2**: loc后缀合并逻辑重复 | `core/suffix_matcher.py:find_suffix_boundaries()` | 共用边界查找 |
| **H3**: POI后缀字典分化 | `dicts/poi_suffix_category.csv` 119+80→131条 | 单一数据源 |
| **H4**: 子进程失败静默 | `launch_parallel()` 检查所有returncode | 失败即终止 |

同步清理:
- 删除 `geomodel/` (无实质代码, pickle兼容层已不需要)
- 删除 v1.1.0 四个词典 (兜底改为 v1.1.1)
- `suffix_seed.csv` 移至 `data/` 目录
- `交接文档.md` → `audit/HANDOVER.md`

三版本质量对比 (2000 loc + 500 org + 500 poi):
- v1.1.1→v1.1.2 地名: 0/2000 差异, 机构名: 0/500 差异, POI: 4/500 差异 (0.8%)
- 重构未引入新的识别误差

## 踩过的坑

1. **multiprocessing + spawn**: macOS Python 3.14 默认 spawn, Pool 不能在 heredoc 中, 必须独立 .py + `__name__` 包裹。最稳方案: bash `&` 16进程

2. **d444 temp字段**: 不是质量分, 是处理阶段标记, 过滤用 org>loc

3. **品牌词/后缀边界**: "美家""骨里香" 在d444中org>loc但实际是品牌, 需手工排除

4. **d1 bare name**: areas/只有全名"北京市", 需展开裸称"北京", 多词可能性取max权重

5. **体系循环**: loc/org/poi 三个系统各自跑全量统计、各自剪枝, 互不混用

6. **抽样≠全量**: Counter看不出d2/d3/d4切分效果, 必须抽查JSONL

7. **org16kw GBK解析**: rsplit(",",5) 取dict字段, 逗号不在最后5列即可

8. **LOCATION→INDUSTRY**: 地名用LOCATION(方位), 机构用INDUSTRY(行业), 拆分避免了同枚举值两含义

9. **POI dict_name**: poi_chunk_stats.py 必须传 dict_name 而非 version, 否则加载org词典导致d1膨胀

10. **aggregate 文件名冲突**: org和poi的aggregate写入了同名 merged_stats.pkl + d2_freqs*.csv, 修复为 org_/poi_ 前缀

11. **短词d4惩罚副作用**: 机构名优化的 freq<50000惩罚 在POI场景误杀短后缀, POI需要 disable_short_d4_penalty=True

12. **POI 训练 bootstrap 字典**: 不能删 poi_v1.1.x 系列, chunk_stats 硬编码 `dict_name` 指向指定版本

## 当前状态

- 系统版本: **v1.2.2**
- 词典版本: **v1.1.2** (当前), v1.1.1 (兜底, **不可删**)
- 总大小: ~18GB
- Python: 3.10+, 纯标准库, 无依赖
