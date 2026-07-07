# HANDOVER.md v1.2.3

> 最后更新: 2026-07-06
> 审计修复: 4 项架构级问题 (H1-H4), 代码净减 248 行
> 详见 `audit/` 目录下 5 份审计报告

## 项目概况

从非结构化中文文本识别地名/机构名/POI/品牌名，四个模组共用 Viterbi DP 引擎。

- 总代码量: ~3200 行 Python, 词典 ~38MB, 数据 ~16GB
- 测试覆盖: **90 条用例**, `python3 -m unittest discover -v -s tests/`
- Python 3.10+, 纯标准库

## 关键文件

### 生产代码

```
pipeline.py          → DictNerPipeline 统一总线
run.py               → CLI 入口
core/config.py       → 共享常量 (VERSION, NUM_CHUNKS, ADDR_TYPES, 路径)
core/types.py        → SegType 枚举 + ADMIN_SUFFIX_MAP + POI_SUFFIX_MAP (从CSV加载)
core/suffix_matcher.py → 后缀边界合并 (find_suffix_boundaries)
loc/                 → 地名: builder.py (构建) + recognizer.py (识别) + importer.py (导入)
org/                 → 机构名: recognizer.py (456行, ORG DP核心)
poi/                 → POI: recognizer.py (19行, thin wrapper)
brand/               → 品牌: model.py (bigram概率)
```

### 训练工具

```
tools/pipeline_base.py    → 共享函数: count_lines, split_file, launch_parallel, aggregate, export_d2_csv
tools/org_launch.py       → org 全量训练 (16并行, ~6min)
tools/org_aggregate.py    → org 聚合+剪枝 (d1≥5, d3≥3, d4≥100)
tools/poi_launch.py       → poi 全量训练 (16并行, ~4min)
tools/poi_aggregate.py    → poi 聚合+剪枝 (d1≥5, d3≥10, d4≥100 + seed)
tools/poi_dedup.py        → A+T 去重 (仅全量重建时需要)
```

### 数据文件

| 文件 | 大小 | 说明 |
|------|------|------|
| `data/split/{loc,org,poi}/` | 10GB | 16chunk分片, 训练直接读取 |
| `data/split/loc/` | 1.9GB | 地名分片 (loc builder 直接读 chunk, 无需源文件) |
| `data/split/org/` | 7.9GB | 机构名分片 |
| `data/split/poi/` | 960MB | POI分片 |
| `data/areas/` | 36MB | 五级行政区划 |
| `data/addr_segments_sql.csv` | 81MB | SQL切分的地址段 (d111) |
| `data/trade_segments_sql.csv` | 1.6MB | SQL切分的行业段 (d333, 死数据) |
| `data/suffix_segments_sql.csv` | 982KB | SQL切分的后缀段 (d444) |
| `data/suffix_seed.csv` | 429KB | POI后缀种子 (从d444提取) |
| `dicts/poi_suffix_category.csv` | 131行 | 后缀→类别映射 |
| `dicts/*v1.1.2.pkl` | 38MB | 当前词典 (4个) |
| `dicts/*v1.1.1.pkl` | 38MB | 兜底词典 (**不可删**) |

## SQL遗存对应表

| SQL旧名 | 新名 | 含义 |
|---------|------|------|
| d1 / d111 | addr_seg | 行政区划段 |
| d2 / d222 | brand_seg | 品牌/专名段 |
| d3 / d333 | trade_seg | 行业属性段 |
| d4 / d444 | suffix_seg | 后缀段 |

## 从零重建

```bash
# 地名词典 (~4min)
python -c "
from loc.builder import DictBuilder
b = DictBuilder('dicts', 'loc_v1.1.2')
b.build_from_loc36kw('data'); b.build_from_areas('data')
b.build_from_d444('data'); b.cleanup()
b.build_orientation_dict(); b.build_location_dict(); b.save()
"

# 机构名 (~6min, 16并行)
python tools/org_launch.py split stats
python tools/org_aggregate.py

# 品牌模型 (~1min)
python -c "
from brand.model import BrandModel
m = BrandModel('dicts', version='v1.1.2')
m.train_from_d2_csv('dicts/iter_v1.1.2/org_d2_freqs_v1.1.2.csv', min_freq=3, min_bigram_count=10)
m.save()
"

# POI (~4min, 16并行。需先运行 poi_dedup.py 生成源文件)
python tools/poi_dedup.py
python tools/poi_launch.py split stats
python tools/poi_aggregate.py
```

## v1.2.2 重构摘要

| 问题 | 方案 | 效果 |
|------|------|------|
| **H1** org/poi 工具链 ~80% 重复 | `core/config.py` + `tools/pipeline_base.py` | 6个文件净减 248 行 |
| **H2** loc后缀合并逻辑重复 | `core/suffix_matcher.py:find_suffix_boundaries()` | 共用边界查找 |
| **H3** POI后缀字典分化 | `dicts/poi_suffix_category.csv` 131条 | 单一数据源 |
| **H4** 子进程失败静默 | `launch_parallel()` 检查 returncode | 失败即终止 |

同步清理:
- 删除 `geomodel/`、`brand_segments_sql.csv`、`loc_corpus.csv`、`poi_deduped.txt`、v1.1.0 四个词典
- 删除 `train_from_d222()` 死方法
- `loc/builder.py` 改为从 `split/loc/` chunk 直接读取
- `poi_launch.py` chunk 存在时自动跳过 dedup+split
- 新增 `tests/` 目录, 90 条用例覆盖 13 个模块

三版本对比 (2000 loc + 500 org + 500 poi):
- v1.1.1→v1.1.2: loc 0/2000, org 0/500, poi 4/500 差异 (0.8%)

## 踩过的坑

1. **multiprocessing + spawn**: macOS Python 3.14 默认 spawn, 必须独立 .py + `__name__` 包裹。最稳方案: bash `&` 16进程
2. **d444 temp字段**: 不是质量分, 是处理阶段标记, 过滤用 org>loc
3. **品牌词/后缀边界**: "美家""骨里香" 在d444中org>loc但实际是品牌, 需手工排除
4. **d1 bare name**: areas/只有全名"北京市", 需展开裸称"北京", 多词可能性取max权重
5. **体系循环**: loc/org/poi 各自跑全量统计、各自剪枝, 互不混用
6. **抽样≠全量**: Counter看不出d2/d3/d4切分效果, 必须抽查JSONL
7. **org16kw GBK解析**: rsplit(",",5) 取dict字段, 逗号不在最后5列即可
8. **LOCATION→INDUSTRY**: 地名用LOCATION(方位), 机构用INDUSTRY(行业), 拆分避免同枚举值两含义
9. **POI dict_name**: poi_chunk_stats.py 必须传 dict_name 而非 version, 否则加载org词典导致d1膨胀
10. **aggregate 文件名冲突**: org和poi的aggregate写入同名文件, 已修复为 org_/poi_ 前缀
11. **短词d4惩罚副作用**: 机构名优化的 freq<50000惩罚 在POI场景误杀短后缀, POI需要 disable_short_d4_penalty=True
12. **POI bootstrap 字典**: 不能删 poi_v1.1.x 系列, chunk_stats 硬编码 `dict_name` 指向指定版本

## 当前状态

- 系统版本: **v1.2.3**, 词典: **v1.1.2** (当前) + v1.1.1 (兜底, **不可删**)
- 测试: **90 用例** 全部通过
- 审计: 四代全部闭环 (v1.0 50/50 + 二代 N1-N24 全部 + 三代 F1-F22 全部 + 四代 Finding 1-19 全部)
