# dict_ner v2.2.1

中文地名/机构名/POI/品牌识别系统。从非结构化中文文本中切分并标注段落类型，支持统一分类 (ORG/POI/ADDR/UNKNOWN)。

## 快速开始

```bash
cd /Users/wainshine/newAI/dict_ner

# 交互识别
python run.py recognize "深圳市南山区华为技术有限公司"

# JSON 输出
python run.py json "北京市朝阳区星巴克咖啡国贸店"

# 统一分类
python run.py classify "广东省卫健委"
python run.py classify --batch file.txt   # 批量分类

# 内置测试集
python run.py test

# 版本信息
python run.py info
```

输出示例：

```
输入: 北京市朝阳区星巴克咖啡国贸店
  地名: [CITY]「北京市」 | [DISTRICT]「朝阳区」 | [POI]「星巴克咖啡国贸店」
  机构: [CITY]「北京市」 | [DISTRICT]「朝阳区」 | [BRAND]「星巴克」 | [INDUSTRY]「咖啡」 | [ORG_SUFFIX]「国贸店」
  POI:  [CITY]「北京市」 | [DISTRICT]「朝阳区」 | [POI]「星巴克」 | [POI]「咖啡」 | [POI]「国贸店」

python run.py classify "深圳市南山区华为技术有限公司"
→ ORG  0.98
```

## 四模组架构

```
输入文本
  │
  ├── loc/ (地名识别)     Viterbi DP + 120万行政词典 + 47万Gaode道路名
  ├── org/ (机构名识别)   四层: 地址+品牌+行业(INDUSTRY)+后缀, 29条gov seed注入
  ├── poi/ (POI识别)     复用机构DP + POI专用词典, 公司后缀自动排除
  └── brand/ (品牌模型)   字级bigram, 90万字符对

pipeline.py  统一总线 + classify() 数据驱动四类判定
run.py       CLI入口
```

### classify() 判定链

```
规则1: 公司/政府后缀在末位 → ORG
规则2: d4 不在 SQL CSV 后缀表中 → 非标准后缀(XX路店) → POI
规则3: d4 精确查 d4_category_map (8,299条Gaode标注) → POI_FAC/POI_STORE/ORG
规则4: d4 endswith 查 suffix_category_gaode (1,520条高置信) → POI_FAC/POI_STORE/ORG
规则5: argmax (geo_cov驱动addr_score, 0.10阈值兜底)
```

## 词典 (v1.2.3, 当前版)

| 词典 | 条目 | 大小 | 说明 |
|------|------|:--:|------|
| `dicts/loc_v1.2.3.pkl` | 120万 + 49万道路 | 31MB | 含 Gaode 道路名, VILLAGE 清理 |
| `dicts/org_v1.2.3.pkl` | d1=64K d3=20K d4=8.3K | 1.8MB | split_polluted_d4 拆分1301条 + gov seed 29条 + POI排除29条 |
| `dicts/poi_v1.2.3.pkl` | d1=48K d3=4.7K d4=16K | 1.1MB | 41条 POI override 注入 |
| `dicts/brand_v1.2.3.pkl` | 90万bigram | 10MB | 基于 v1.2.3 org d2 CSV 训练 |

### 数据驱动表（运行时加载）

| 文件 | 条目 | 说明 |
|------|------|------|
| `dicts/d4_category_map.pkl` | 8,299 | org d4 全量 Gaode 标注 (ORG/POI_FAC/POI_STORE/ADDR/AMBIGUOUS) |
| `dicts/suffix_category_gaode.csv` | 1,520 | 高置信后缀→类别 (仅保留在 suffix_segments_sql.csv 中的后缀) |

> v1.1.2 + v1.2.0 + v1.2.2 版本保留在 `dicts/` 中作为兜底和对比基准。

## 目录结构

```
dict_ner/
├── core/                共享类型和常量 (SegType, Trie, config, suffix_matcher, csv_index)
├── loc/                 地名识别器 + 词典构建器
├── org/                 机构名识别器
├── poi/                 POI识别器 (thin wrapper over org DP)
├── brand/               品牌词概率模型
├── pipeline.py          统一识别总线 + classify()
├── run.py               CLI 入口
├── eval.py              评估脚本
├── scripts/             数据扫描脚本
│   ├── build_gaode_index.py  Gaode 67文件单次扫描 → 3数据产物
│   └── validate_d4_map.py    d4_category_map vs SQL CSV 一致性校验
├── tools/               训练/迭代工具
│   ├── org_launch.py / org_chunk_stats.py / org_aggregate.py
│   ├── poi_launch.py / poi_chunk_stats.py / poi_aggregate.py / poi_dedup.py
│   ├── pipeline_base.py (共享pipeline函数)
│   ├── merge_gaode_roads.py (Gaode道路名合并入LOC词典)
│   ├── clean_loc_villages.py (VILLAGE清理, 依据areas/)
│   ├── build_eval_set.py (按type比例采样+自然地名)
│   ├── eval_classify.py (分类评测)
│   ├── extract_badcase.py / eval_badcase.py / eval_badcase_pipeline.py (badcase工具)
│   ├── org_eval_launch.py / poi_eval_launch.py / loc_eval_launch.py (分片评估)
│   ├── rebuild_stats_launch.py (stats重建)
│   ├── org_eval.py / org_sample_jsonl.py
│   ├── org_compare_launch.py / org_process_worker.py (多版本对比)
├── data/                语料与分片
│   ├── addr/trade/suffix_segments_sql.csv (三SQL表)
│   ├── gov_suffix_seed.csv (29条政府后缀种子)
│   ├── gaode_roads.csv (47万Gaode道路名)
│   ├── eval_set.csv (18万条评测集)
│   ├── areas/ (五级行政区划)
│   ├── 高德amap/ (67文件, 11GB)
│   ├── 腾讯地图/ (345文件, 7.5GB)
│   └── split/{loc,org,poi}/ (16 chunk 分片)
├── dicts/               词典
│   ├── *v1.2.3.pkl (4个, 当前版)
│   ├── *v1.2.2.pkl (4个, 上一版)
│   ├── *v1.2.0.pkl (4个, 对比基线)
│   ├── *v1.1.2.pkl (4个, 兜底版)
│   ├── d4_category_map.pkl (8,299条d4 Gaode标注)
│   ├── suffix_category_gaode.csv (1,520条高置信后缀)
│   ├── poi_suffix_category.csv (131条后缀→类别映射)
│   └── iter_v1.2.2/ iter_v1.2.3/ (统计中间产物)
├── audit/               审计报告
│   ├── HANDOVER.md      交接手册
│   ├── v2.2.1_refactor_plan.md
│   ├── v2.2_refactor_plan.md
│   ├── v2.1_refactor_plan.md
│   └── v2.0_refactor_plan.md
└── tests/               112 条用例 (16个文件)
```

## 识别质量

### 分类评测 (18万条, v2.2.1 vs baseline)

| 指标 | v2.2.1 | baseline v1.2.3 | Delta |
|------|:---:|:---:|:---:|
| macro-F1 | 0.3702 | 0.3513 | **+0.0189** |
| ORG F1 | 0.5203 | 0.3925 | **+0.1278** |
| POI F1 | 0.5419 | 0.6599 | -0.1180 |
| ADDR F1 | 0.4163 | 0.3529 | +0.0634 |

### 传统指标

| 指标 | 值 |
|------|:--:|
| 地名 Score | 62.6 (5000条采样, v1.1.2) |
| 机构 OK 率 | 93.3% (2万条采样) |
| 品牌分离度 | 4.1 log-units |

## 完整重建流程

### 1. 数据扫描 (~30min, 一次性)

```bash
python scripts/build_gaode_index.py
# 产出: dicts/d4_category_map.pkl + dicts/suffix_category_gaode.csv + data/gaode_roads.csv
```

### 2. 地名词典 (~6min)

```bash
python -c "
from loc.builder import DictBuilder
b = DictBuilder('dicts', 'loc_v1.2.3')
b.build_from_loc36kw('data'); b.build_from_areas('data')
b.build_from_d444('data'); b.cleanup()
b.build_orientation_dict(); b.build_location_dict(); b.save()
"
python tools/merge_gaode_roads.py   # 合并47万Gaode道路名 + 相邻道路拆分
python tools/clean_loc_villages.py  # 依据areas/五级行政区划清理VILLAGE误标
```

### 3. 机构名词典 (~12min)

```bash
# 版本号: 修改 core/config.py VERSION="v1.2.3"
mkdir -p dicts/iter_v1.2.3
cp dicts/iter_v1.2.2/org_stats_*.pkl dicts/iter_v1.2.3/   # 首次用旧版stats

python tools/org_launch.py split stats       # split 仅首次, stats 并行
python tools/org_aggregate.py                # 含 split_polluted_d4 + gov_seed(29条) + POI_EXCLUDE_D4(29条)
```

### 4. POI 词典 (~4min)

```bash
cp dicts/iter_v1.2.2/poi_stats_*.pkl dicts/iter_v1.2.3/

python tools/poi_dedup.py                    # 仅首次
python tools/poi_launch.py split stats       # split 仅首次
python tools/poi_aggregate.py                # 含 POI override 注入
```

### 5. 品牌模型 (~1min)

```python
from brand.model import BrandModel
model = BrandModel('dicts', version='v1.2.3')
model.train_from_d2_csv("dicts/iter_v1.2.3/org_d2_freqs_v1.2.3.csv", min_freq=3, min_bigram_count=10)
model.save()
```

### 6. 版本跟进

```bash
# core/config.py: VERSION = "v1.2.3"
# pipeline.py: __init__ 默认 loc_v1.2.3 / v1.2.3 / poi_v1.2.3 / t_unknown=0.10
# tests/test_dict_snapshot.py, test_config.py: 版本号同步

python -m unittest discover -v -s tests/     # 112 全绿
```

---

## 评估体系

### 分片语料全量评估 (段文本差异 + 类型分布 + 序列分布)

```bash
# ORG (~6min/版本)
python tools/org_eval_launch.py run          # 16并行, 产出 output/org_eval/org_v1.2.x/ (JSONL+stats)
python tools/org_eval_launch.py compare      # → output/org_eval/org_eval_report.md

# POI (~1.5min/版本)
python tools/poi_eval_launch.py run
python tools/poi_eval_launch.py compare      # → output/poi_eval/poi_eval_report.md

# LOC (~3min/版本)
python tools/loc_eval_launch.py run
python tools/loc_eval_launch.py compare      # → output/loc_eval/loc_eval_report.md
```

报告含：覆盖率（段分布）+ 全量段类型分布 + 段文本逐条差异（chunk_00）+ 段类型序列分布（1~6段）

### classify 评测 (18万条)

```bash
python tools/build_eval_set.py               # Gaode按type比例(10万)+Tencent(5万)+自然地名(3万) → eval_set.csv
python tools/eval_classify.py --eval data/eval_set.csv --baseline baseline.json
# → 混淆矩阵4x4 + per-class P/R/F1 + macro-F1 + delta
```

### Badcase 评估

```bash
# 提取低频序列 (<10次) 作为 baseline badcase 集
python tools/extract_badcase.py --eval org --max-freq 10 --version v1.2.2
# → data/badcase_org_v1.2.2.csv

# Pipeline 层 badcase 评测 (测复合检测+过度拆分合并效果)
python tools/eval_badcase_pipeline.py --badcase data/badcase_org_v1.2.2.csv \
  --versions v1.2.2,v1.2.3 --eval org
# → REPAIRED/STILL_LOW/CHANGED 统计
```

### 多版本段对比 (ORG/POI/LOC)

```bash
python tools/org_compare_launch.py run       # 16并行, 对52M公司名name跑多个版本
python tools/org_compare_launch.py compare   # → output/org_compare/org_compare_report.md
```

### SQL CSV 校验

```bash
python scripts/validate_d4_map.py            # d4_category_map vs suffix_segments_sql.csv
# → STRONG_AGREE / WEAK_AGREE / CONFLICT / UNTESTABLE 分类
```

### 迭代工作流

```
改代码/改词典
    │
    ├── python -m unittest discover -v -s tests/       → 112条全绿
    ├── tools/org_eval_launch.py compare               → 段文本差异 + 序列分布
    ├── tools/eval_classify.py --eval data/eval_set.csv  → macro-F1 + per-class F1
    ├── tools/eval_badcase_pipeline.py                 → badcase 修复率
    └── tools/poi_eval_launch.py compare / tools/loc_eval_launch.py compare
    │
    v
对比 baseline → 升级 / 回滚
```

## 段类型说明

| 类型 | 含义 | 识别器 |
|------|------|--------|
| PROVINCE/CITY/DISTRICT/TOWN/VILLAGE/COMMUNITY/ROAD | 行政区划 | loc |
| LOCATION | 方位/位置描述 | loc |
| ORG_SUFFIX | 机构后缀段 (原 org 输出 POI) | org |
| POI | POI后缀 | org/poi |
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
| `tests/test_dict_snapshot.py` | 6 | 词典快照 |
| `tests/test_short_d4_penalty.py` | 3 | N17: 短词d4惩罚 |
| `tests/test_classify.py` | 12 | v2.2: 分类判断 |
| `tests/test_csv_index.py` | 6 | v2.2: 亲和度索引 |
| `tests/test_d4_map.py` | 4 | v2.2: d4标注质量 |
| **总计** | **112** | |

## 踩过的坑

1. **macOS spawn 模式**: Pool 子进程必须独立 .py 文件 + `if __name__ == '__main__'`, 最稳方案是 bash `&` 16进程后台
2. **d444 temp 字段**: 不是质量分, 是SQL处理阶段标记, 不要用来过滤
3. **体系循环**: loc/org/poi 三个系统的后缀词典各自演化, 互不混用
4. **d111 注入**: 只能fallback时用, POI用dict_name独立加载后必须跳过
5. **LOCATION 语义混用**: 地名用LOCATION(方位), 机构用INDUSTRY(行业), 通过SegType分离
6. **POI dict_name vs version**: POI训练时必须传dict_name而非version, 否则加载org词典
7. **suffix_segments_sql.csv 无法区分ORG/POI**: org_ratio 衡量语料出现频率而非实体类型。"超市" org_ratio=1.0 (机构语料中常见) 但实际是POI。v2.2 用Gaode d4_category_map 覆盖此盲区
8. **d4∉SQL CSV → POI 规则**: "XX黄河路店"中 d4="店"不在SQL CSV后缀表中 → 非标准后缀 → 地址信息嵌入名称 → POI
9. **道路名复合名**: Gaode address 中"药王路与香山路"被正则误匹配, 需拆分为"药王路"和"香山路"分别统计
10. **单字符后缀缺失**: "店""馆"不在 suffix_segments_sql.csv (d4要求 len≥2), 需在 suffix_category_gaode.csv 手动补入

## 版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| **v2.2.1** | 2026-07-11 | 段类型体系修复 (SegType.ORG_SUFFIX)。split_polluted_d4 拆分1301条 d4→d3+d4。POI_EXCLUDE_D4 精简(41→29)。_decide 查表调score。LOC VILLAGE 清理(石家庄/枣庄→CITY)。复合机构检测+重识别。过度拆分合并(SQL CSV校验)。badcase 体系。评测18万条, macro-F1=0.3702。词典 v1.2.3。测试112条。 |
| **v2.2.0** | 2026-07-11 | 数据驱动 classify: d4_category_map (9,577条Gaode标注) + suffix_category_gaode (1,520条高置信后缀)。移除手工后缀列表。SQL CSV 规则 (d4∉SQL→POI)。Gaode道路名合并入LOC词典 (47万条)。gov seed 29条。 |
| v2.1.0 | 2026-07-10 | `pipeline.classify()` 统一分类: ORG/POI/ADDR/UNKNOWN。csv_index 亲和度评分。gov suffix seed 注入。评测闭环。手工后缀列表驱动。词典 v1.2.1。测试108条。待修复的问题在 v2.2 解决。 |
| v1.2.3 | 2026-07-07 | 四代审计 F1-F22 全部修复 + Finding 1-19 全部修复。F1/F3/F7 三次迭代回归修正。Trie 碰撞优先级、线程安全、LOC 裸名、gbk fallback、original 字段一致性。测试 90 条 |
| v1.2.2 | 2026-07-06 | 架构重构: H1-H4 + 二代审计 N1-N24 全部修复。新增 `core/config.py`, `core/suffix_matcher.py`, `tools/pipeline_base.py`。删除 `geomodel/`。词典升级至 v1.1.2。测试 77 条 |
| v1.2.1 | 2026-07-06 | 审计修复: 22/50 (Critical 2, High 4, Medium 10, Low 6) |
| v1.1.1 | — | 词典收敛版: 四词典统一 v1.1.1, brand 分离度 4.1, poi d4 覆盖 113% |
| v1.1.0 | — | 初版收敛词典 |
