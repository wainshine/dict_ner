# dict_ner v1.2.3

中文地名/机构名/POI/品牌识别系统。从非结构化中文文本中切分并标注段落类型。

## 快速开始

```bash
cd /Users/wainshine/newAI/dict_ner

# 交互识别
python run.py recognize "深圳市南山区华为技术有限公司"

# JSON 输出
python run.py json "北京市朝阳区星巴克咖啡国贸店"

# 内置测试集
python run.py test

# 版本信息
python run.py info
```

输出示例：

```
输入: 北京市朝阳区星巴克咖啡国贸店
  地名: [CITY]「北京市」 | [DISTRICT]「朝阳区」 | [POI]「星巴克咖啡国贸店」
  机构: [CITY]「北京市」 | [DISTRICT]「朝阳区」 | [POI]「星巴克」 | [INDUSTRY]「咖啡」 | [POI]「国贸店」
  POI:  [CITY]「北京市」 | [DISTRICT]「朝阳区」 | [POI]「星巴克」 | [POI]「咖啡」 | [POI]「国贸店」
```

## 四模组架构

```
输入文本
  │
  ├── loc/ (地名识别)     Viterbi DP + 120万行政词典
  ├── org/ (机构名识别)   四层: 地址+品牌+行业(INDUSTRY)+后缀
  ├── poi/ (POI识别)     复用机构DP + POI专用词典, 公司后缀自动排除
  └── brand/ (品牌模型)   字级bigram, 90万字符对, 分离度4.1

pipeline.py  统一总线
run.py       CLI入口
```

## 词典 (v1.1.2, 当前版)

| 词典 | 条目 | 大小 | 说明 |
|------|------|:--:|------|
| `dicts/loc_v1.1.2.pkl` | 120万 | 25MB | 省/市/区/镇/村/路 10类 |
| `dicts/org_v1.1.2.pkl` | d1=64K d3=20K d4=9.6K | 1.8MB | d1≥5阈值 |
| `dicts/poi_v1.1.2.pkl` | d1=44K d3=4.8K d4=16K | 1.2MB | d1≥5 d3≥10 |
| `dicts/brand_v1.1.2.pkl` | 90万bigram | 10MB | 分离度4.1 |

> v1.1.1 版本保留在 `dicts/` 中作为兜底。

## 目录结构

```
dict_ner/
├── core/                共享类型和常量 (SegType, Trie, config, suffix_matcher)
├── loc/                 地名识别器 + 词典构建器
├── org/                 机构名识别器
├── poi/                 POI识别器 (thin wrapper over org DP)
├── brand/               品牌词概率模型
├── pipeline.py          统一识别总线
├── run.py               CLI 入口
├── eval.py              评估脚本
├── tools/               训练/迭代工具
│   ├── org_launch.py / org_chunk_stats.py / org_aggregate.py
│   ├── poi_launch.py / poi_chunk_stats.py / poi_aggregate.py / poi_dedup.py
│   ├── pipeline_base.py (共享pipeline函数, org/poi 去重后提取)
│   ├── org_eval.py / org_sample_jsonl.py
├── data/                语料与分片
│   ├── addr/trade/suffix_segments_sql.csv
│   ├── suffix_seed.csv (POI后缀种子, 429KB)
│   ├── areas/ (五级行政区划)
│   ├── 公司名input.txt (1.2GB, 备用语料)
│   ├── 地名A/T input.txt (测试集)
│   └── split/{loc,org,poi}/ (16 chunk 分片)
├── dicts/               词典
│   ├── *v1.1.2.pkl (4个, 当前版)
│   ├── *v1.1.1.pkl (4个, 兜底版)
│   └── poi_suffix_category.csv (131条后缀→类别映射)
├── audit/               审计报告 (50条问题清单 + 修复建议)
│   └── HANDOVER.md      交接手册
└── output/
    └── org_sample_100k.jsonl (10万条机构识别样本)
```

## 识别质量

| 指标 | 值 |
|------|:--:|
| 地名 Score | 62.6 (5000条采样, v1.1.2) |
| 机构 OK 率 | 93.3% (2万条采样) |
| 机构 d2_as_d4 | 3.6% |
| POI d4 覆盖 | 113% |
| POI d2 污染 | 0 (10类均已过滤) |
| 品牌分离度 | 4.1 log-units |

## 如何训练

### 地名 (~4min)

```bash
python -c "
from loc.builder import DictBuilder
b = DictBuilder('dicts', 'loc_v1.1.2')
b.build_from_loc36kw('data'); b.build_from_areas('data')
b.build_from_d444('data'); b.cleanup()
b.build_orientation_dict(); b.build_location_dict(); b.save()
"
```

### 机构名 (16并行, ~6min)

```bash
python tools/org_launch.py split stats
python tools/org_aggregate.py
```

### 品牌模型 (~1min)

```python
from brand.model import BrandModel
model = BrandModel('dicts', version='v1.1.2')
model.train_from_d2_csv("dicts/iter_v1.1.2/org_d2_freqs_v1.1.2.csv", min_freq=3, min_bigram_count=10)
model.save()
```

### POI (16并行, ~4min)

```bash
python tools/poi_dedup.py              # 去重
python tools/poi_launch.py split stats
python tools/poi_aggregate.py
```

## 段类型说明

| 类型 | 含义 | 识别器 |
|------|------|--------|
| PROVINCE/CITY/DISTRICT/TOWN/VILLAGE/COMMUNITY/ROAD | 行政区划 | loc |
| LOCATION | 方位/位置描述 | loc |
| POI | 机构/POI后缀 | org/poi |
| INDUSTRY | 行业/业态类别 | org/poi |
| BRAND | 专名/品牌段 | org/poi |
| UNKNOWN | 未识别 | loc |
| ORIENTATION | 方向词 | loc |
| NUMERIC | 数字 | loc |

## 依赖

Python 3.10+, 纯标准库 (无第三方依赖)。

## 测试

```bash
cd /Users/wainshine/newAI/dict_ner
python3 -m unittest discover -v -s tests/
```

| 文件 | 用例 | 类型 |
|------|:--:|------|
| `tests/test_suffix_matcher.py` | 7 | P1: 后缀边界合并 |
| `tests/test_importer.py` | 15 | P1: _split_admin + classify_suffix |
| `tests/test_loc_builder.py` | 2 | P1: chunk 加载 |
| `tests/test_pipeline_base.py` | 8 | P1: 共享 pipeline 函数 |
| `tests/test_loc_recognizer.py` | 8 | P2: 地名识别 (真实词典) |
| `tests/test_org_recognizer.py` | 9 | P2: 机构名识别 (真实词典) |
| `tests/test_brand_model.py` | 6 | P2: 品牌模型 (真实模型) |
| `tests/test_types.py` | 10 | P3: 枚举/类型 |
| `tests/test_config.py` | 6 | P3: 路径常量 |
| `tests/test_pipeline.py` | 8 | P3: 集成+POI |
| `tests/test_confidence.py` | 2 | N10: 段级置信度 |
| `tests/test_dict_snapshot.py` | 6 | N23: 词典快照 |
| `tests/test_short_d4_penalty.py` | 3 | N17: 短词d4惩罚 |
| **总计** | **90** | |

## 踩过的坑

1. **macOS spawn 模式**: Pool 子进程必须独立 .py 文件 + `if __name__ == '__main__'`, 最稳方案是 bash `&` 16进程后台
2. **d444 temp 字段**: 不是质量分, 是SQL处理阶段标记, 不要用来过滤
3. **体系循环**: loc/org/poi 三个系统的后缀词典各自演化, 互不混用
4. **d111 注入**: 只能fallback时用, POI用dict_name独立加载后必须跳过
5. **LOCATION 语义混用**: 地名用LOCATION(方位), 机构用INDUSTRY(行业), 通过SegType分离
6. **POI dict_name vs version**: POI训练时必须传dict_name而非version, 否则加载org词典

## 版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.2.3 | 2026-07-07 | 四代审计 F1-F22 全部修复 + Finding 1-19 全部修复。F1/F3/F7 三次迭代回归修正。Trie 碰撞优先级、线程安全、LOC 裸名、gbk fallback、original 字段一致性。测试 90 条 |
| v1.2.2 | 2026-07-06 | 架构重构: H1-H4 + 二代审计 N1-N24 全部修复。新增 `core/config.py`, `core/suffix_matcher.py`, `tools/pipeline_base.py`。删除 `geomodel/`。词典升级至 v1.1.2。测试 77 条 |
| v1.2.1 | 2026-07-06 | 审计修复: 22/50 (Critical 2, High 4, Medium 10, Low 6) |
| v1.1.1 | — | 词典收敛版: 四词典统一 v1.1.1, brand 分离度 4.1, poi d4 覆盖 113% |
| v1.1.0 | — | 初版收敛词典 |
