# dict_ner v4.0.1

中文地名/机构名/POI/品牌识别系统。从非结构化中文文本中切分并标注段落类型，统一分类为 ORG/POI/ADDR/UNKNOWN 四类，输出校准置信度。

- 系统版本: **v4.0.1** | 词典: **v1.5.0**（四词典统一编号） | 测试: **181 条全绿**
- 完整版本历史: [CHANGELOG.md](CHANGELOG.md) | 接手手册: [audit/HANDOVER.md](audit/HANDOVER.md) | 新会话速通: [AGENTS.md](AGENTS.md)

## 文档体系（定位与维护原则）

| 文档 | 定位 | 更新时机 |
|------|------|---------|
| `README.md`（本文件） | 门面：是什么/怎么用/效果多少 | 每次发版同步 |
| `audit/HANDOVER.md` | 接手手册：架构/管线/数据血缘/门禁/决策记录/踩坑 | 每次发版同步 |
| `CHANGELOG.md` | 版本历史唯一来源 | 每次发版新增一节 |

原则：① 版本历史只写 CHANGELOG，README 和 HANDOVER 不重复记录变更明细；② 架构/流程/决策只写 HANDOVER，README 放简版；③ 三文档版本号必须一致，发版时一并提交。

## 快速开始

```bash
cd /Users/wainshine/newAI/dict_ner
pip install -r requirements.txt   # v3 需要 sklearn/numpy/pandas; serve 需要 fastapi/uvicorn

# 分类 (v3 GBDT 模型, 默认入口)
python run.py classify "深圳市南山区华为技术有限公司"     # → ORG 0.98
python run.py classify --batch file.txt                  # 批量 (1.4ms/条)

# 段切分 (三体系视图)
python run.py recognize "北京市朝阳区星巴克咖啡国贸店"
python run.py json "北京市朝阳区星巴克咖啡国贸店"

# 旧版规则链 (v2 冻结 baseline, pipeline_v2.py + /v2/)
python run.py v2 classify "广东省卫健委"

# HTTP 服务 (FastAPI)
uvicorn serve:app --host 0.0.0.0 --port 8000 --workers 4
#   POST /classify {"text": ...}  POST /classify_batch {"texts": [...]}  GET /health

python run.py info
```

输出示例：

```
输入: 北京市朝阳区星巴克咖啡国贸店
  地名: [CITY]「北京市」 | [DISTRICT]「朝阳区」 | [POI]「星巴克咖啡国贸店」
  机构: [CITY]「北京市」 | [DISTRICT]「朝阳区」 | [BRAND]「星巴克」 | [INDUSTRY]「咖啡」 | [ORG_SUFFIX]「国贸店」
  POI:  [CITY]「北京市」 | [DISTRICT]「朝阳区」 | [POI]「星巴克」 | [POI]「咖啡」 | [POI]「国贸店」
```

## 系统架构

```
输入文本
  │
  ├─ v3/engine/  统一 Viterbi DP 引擎 (Trie + 转移代价 + 钩子链, 三套配置)
  │     loc 引擎: 行政区划/道路/LOCATION/NUMERIC/POI_SUB
  │     org 引擎: d1地址段 + d3行业段 + d4后缀段
  │     poi 引擎: 同构, POI 专用词典 + 宽松约束
  │
  ├─ v3/pipeline.py  V3Pipeline 总线
  │     后处理: ORG_SUFFIX remap / 过度拆分合并 / 复合机构重识别 /
  │             TOWN-BRAND 裁决 / 括号归并
  │     查表: d4_category_map / suffix_category_gaode / SQL 三表亲和度
  │
  ├─ v3/features.py  78 维特征 (段级/查表/统计/规则信号)
  │
  └─ GBDT 分类器 (models/clf_v3.pkl, 500树×4类 + isotonic 校准)
        v3/fast_predict.py 编译化推理 (numpy 树遍历, 与 sklearn 零误差)
        输出: category + 校准 confidence + best 段切分
```

## 词典 (v1.5.0, 当前版)

| 词典 | 条目 | 大小 | 说明 |
|------|------|:--:|------|
| `dicts/loc_v1.5.0.pkl` | VILLAGE 449K / ROAD 424K / COMMUNITY 228K / CITY 90K / TOWN 67K | 29MB | NUMERIC/POI_SUB 从零建模 |
| `dicts/org_v1.5.0.pkl` | d1=57K d3=20K d4=8.7K | 1.5MB | v1.4.3 引擎重统词频 + 补丁固化 |
| `dicts/poi_v1.5.0.pkl` | d1=49K d3=4.7K d4=23.6K | 1.2MB | 位置证据剪枝 (203 词 d1→d4) |
| `dicts/brand_v1.5.0.pkl` | 91万 bigram | 9.7MB | 基于 v1.5.0 org d2 统计重训 |

**统一版本号政策**：任一词典变更，四词典版本号一起升。旧版保留：v1.2.x（v2 baseline）、v1.1.x（兜底，不可删）。

**可读审计面**：`dicts/export/{org,poi}_{d1,d3,d4}_export.csv` 词频表，可直接人工抽查。

### 运行时数据表

| 文件 | 条目 | 用途 |
|------|-----:|------|
| `dicts/d4_category_map.pkl` | 8,299 | org d4 全量 Gaode 标注 (分类特征) |
| `dicts/suffix_category_gaode.csv` | 1,520 | 高置信后缀→类别 (分类特征/误杀回补依据) |
| `data/{addr,trade,suffix}_segments_sql.csv` | 200万/4万/2.4万 | SQL 时代三表 (质量过滤+亲和度特征) |

## 识别质量

### 分类评测 (test 集 38,514 条, 一次性)

| 指标 | v4.0.x (当前) | v2.2.1 规则链 |
|------|:---:|:---:|
| macro-F1 | **0.9059** | 0.3702 |
| accuracy | **0.9056** | 0.4463 |
| ORG F1 | 0.8666 | 0.5203 |
| POI F1 | 0.9060 | 0.5419 |
| ADDR F1 | 0.9214 | 0.4163 |
| UNKNOWN F1 | 0.9296 | 0.0024 |

### 三视角补充指标

| 视角 | 值 | 说明 |
|------|---|------|
| clean 子集 accuracy | **0.9919** | 查表确认标签的子集 (近真实上限; 含噪标签占 ~13%) |
| ORG 纯净召回 | 73.9% | org_company 5200万公司名抽样100万; "误判"为个体户门店 (语义边界) |
| POI 纯净召回 | 57.5% | split/poi 4000万抽样100万; "误判"为机构网点 (语义边界) |
| 置信度校准 | ECE=0.0129 | confidence 可直接作概率路由 |

### 段健康度 (20万样本, `v3/seg_quality.py`)

| 指标 | 值 |
|------|---:|
| org 末段 ORG_SUFFIX 率 | 97.8% |
| org 后缀验证率 / 行业验证率 | 97.9% / 99.3% |
| org 地址验证率 | **98.6%** |
| LOC unknown 字符率 | 3.4% |
| 低频序列率 (org) | 4.4% |

## 目录结构

```
dict_ner/
├── v3/                    v3 系统 (当前生产路径)
│   ├── engine/            统一 DP 引擎 (dp.py + configs.py) + gate.py 门禁
│   ├── features.py        78 维特征提取
│   ├── pipeline.py        V3Pipeline 总线 (v4.0.0 起自包含, 不再依赖 v2)
│   ├── brand_model.py     品牌 bigram 模型 (v3 自有副本)
│   ├── infer.py           V3Classifier 推理
│   ├── fast_predict.py    HistGBDT 编译化快速预测器
│   ├── train.py / labels.py / sample_pool.py / sample_unknown.py   训练链
│   ├── precompute.py / precompute_worker.py                        16进程特征预计算
│   ├── synth_unknown.py / clean_eval.py / calibration_audit.py     数据与评估
│   ├── evaluate.py / pure_eval.py / seg_quality.py                 评估
│   ├── seg_compare.py / eval_cut.py / badcase_eval.py              段级对比评估
│   ├── seq_dist_compare.py / loc_prune.py / poi_prune.py / bare_prune.py  词典挖掘
│   └── seg_compare_worker.py / eval_cut_worker.py / pure_eval_worker.py
├── v2/                  v2 冻结 baseline (v4.0.0 起平铺迁移至此)
│   ├── loc_recognizer.py / loc_builder.py / loc_importer.py
│   ├── org_recognizer.py / poi_recognizer.py / brand_model.py / eval.py
│   └── tools/             v2 时代训练/评估工具 (launch/worker/eval 系列)
├── core/                共享类型和常量 (SegType, Trie, config, csv_index, suffix_matcher, suffix_classify)
├── pipeline_v2.py       v2 统一总线 (冻结 baseline, run.py v2 使用)
├── run.py               CLI 入口
├── serve.py             FastAPI 服务 (POST /classify /classify_batch, GET /health)
├── models/              GBDT 模型 (clf_v3.pkl + manifest)
├── dicts/               词典 (v1.5.0 当前 + 历史版本 + export/ 审计表 + iter_v1.5.0/ 统计中间产物)
├── data/                语料与切分 (split/ 四套语料, SQL 三表, eval splits, Gaode/腾讯原始数据)
├── scripts/             数据扫描 (build_gaode_index / validate_d4_map)
├── tools/               v3 时代训练与词典工具 (stats_v3 / aggregate / patch_v14x / bake / pipeline_base)
├── audit/               HANDOVER.md + 各代审计/方案报告
├── tests/               181 条用例 (tests/legacy/ 71 条 v2 锚定 + 根目录 110 条 v3/core/serve)
└── CHANGELOG.md         完整版本历史
```

## 完整重建流程 (v1.5.0 链)

```bash
# 1. stats 重切 (v3 引擎 bootstrap, ~20min)
STATS_VERSION=v1.4.3 python3 tools/stats_launch_v3.py     # → dicts/iter_v1.5.0/

# 2. aggregate (~10min)
DICT_VERSION=v1.5.0 python3 tools/org_aggregate.py
DICT_VERSION=v1.5.0 python3 tools/poi_aggregate.py

# 3. 补丁固化 (括号/误杀回补/数字垃圾/村委会复合词/d3低频)
python3 v3/poi_prune.py --dict poi_v1.5.0.pkl --out dicts/poi_prune_v1.5.0.json --chunks 4
python3 tools/patch_v141.py --src-v v1.5.0 --dst-v v1.5.0
python3 tools/patch_v142.py --src-v v1.5.0 --dst-v v1.5.0
# bake 含 bare 注入互斥, 见 HANDOVER §2.2

# 4. loc 词典 (builder + 道路 + VILLAGE 清理 + prune/注入)
python3 tools/loc_build_v140.py       # 改版本号复用
python3 tools/merge_gaode_roads.py    # freq≥10
python3 tools/clean_loc_villages.py

# 5. brand 模型 (~2min)
python3 -c "
from v3.brand_model import BrandModel
m = BrandModel('dicts', version='v1.5.0')
m.train_from_d2_csv('dicts/iter_v1.5.0/org_d2_freqs_v1.5.0.csv', min_freq=3, min_bigram_count=10)
m.save()"

# 6. 分类器重训 (~15min)
python3 v3/precompute.py all data/v3_train_pool.csv output/v3_feat/pool_feats.csv
python3 v3/labels.py --pool output/v3_feat/pool_feats.csv --drop-org 0.55 --drop-poi 0.55 --drop-addr 0.65 --flip 0.9
python3 v3/train.py --train output/v3_feat/final_train3.csv --calib-set output/v3_feat/train_feats.csv

# 7. 门禁
python3 v3/engine/gate.py --n 20000        # 引擎一致性
python3 v3/seg_quality.py --engine org --n 200000 --v3
python3 -m unittest discover -v -s tests/  # 181 全绿
```

## 评估体系

| 工具 | 用途 | 产物 |
|------|------|------|
| `v3/evaluate.py` | 混淆矩阵 + 错误仪表盘 | output/v3_error_report.md |
| `v3/clean_eval.py` | clean 子集双指标 (模型无关标签确认) | 终端 |
| `v3/pure_eval.py` | 纯净集召回 (org_company / split_poi) | output/v3_pure_eval_report.md |
| `v3/calibration_audit.py` | 置信度可靠性 (ECE/Brier) | output/v3_calibration_report.md |
| `v3/seg_quality.py` | 段健康度 (后缀/行业/地址验证率/低频序列) | output/v3_seg_*.json |
| `v3/seg_compare.py` | 两版词典全量段对比 | output/v3_seg_compare_report.md |
| `v3/eval_cut.py` | 全量重切产出 JSONL+stats | output/*_eval/*_vX/ |
| `v3/badcase_eval.py` | badcase 跨版修复率 | output/v*_badcase_*.md |
| `v3/engine/gate.py` | 引擎一致性门禁 (新旧零差异) | 终端 |
| `v2/tools/eval_classify.py` | v2 规则链评测 (baseline 对比) | 终端/JSON |

## 迭代工作流

```
改词典 / 改引擎 / 改分类器
    │
    ├─ python3 -m unittest discover -s tests/     → 181 全绿
    ├─ v3/seg_quality.py (三体系)                  → 段健康度不降
    ├─ v3/seg_compare.py (新旧全量对比)            → diff 逐类审查
    ├─ v3/evaluate.py --feats val_feats.csv       → val macro-F1 不降
    └─ v3/badcase_eval.py                          → 修复率
    │
    v
词典版本号四同升 (统一版本政策) → 全链路重训 → 文档三件套更新 → 提交
```

## 段类型说明

| 类型 | 含义 | 识别器 |
|------|------|--------|
| PROVINCE/CITY/DISTRICT/TOWN/VILLAGE/COMMUNITY/ROAD | 行政区划 | loc |
| LOCATION / ORIENTATION | 方位/位置描述 | loc |
| NUMERIC | 数字段 (门牌/楼层) | loc |
| POI_SUB | 子级点位 (号/层/栋/组) | loc |
| ORG_SUFFIX | 机构后缀段 | org |
| POI | POI后缀 | org/poi |
| INDUSTRY | 行业/业态类别 | org/poi |
| BRAND | 专名/品牌段 | org/poi |
| UNKNOWN | 未识别 | loc |

## 依赖与测试

Python 3.10+。v2 模块 (`/v2/` + `pipeline_v2.py`) 纯标准库；`v3/` 需 scikit-learn≥1.5, numpy, pandas；`serve.py` 需 fastapi, uvicorn。

```bash
python3 -m unittest discover -v -s tests/    # 181 条 (tests/legacy/ 71 + 根目录 110)
```

## 版本记录

最近版本（完整历史见 [CHANGELOG.md](CHANGELOG.md)）：

| 版本 | 日期 | 一句话 |
|------|------|------|
| **v4.0.1** | 2026-08-05 | 迁移后审计 + v3 测试补齐 124→181 |
| **v4.0.0** | 2026-08-05 | v2 代码迁移 /v2/ + pipeline_v2.py + FastAPI serve.py 生产化 |
| **v3.9.2** | 2026-08-05 | AGENTS.md 速通 + v4.0.0 迁移计划 + 磁盘治理 5GB |
| **v3.9.1** | 2026-08-05 | 文档体系重构 (README/HANDOVER/CHANGELOG 三件套) |
| **v3.9.0** | 2026-08-04 | 置信度审计合格 + TOWN/BRAND 裁决 + v1.5.0 自举收敛, test 0.9059 |
| **v3.8.0** | 2026-08-04 | 统一版本号 + FastGBDT 30× + 纯净集评测 + bare 攻坚 |
