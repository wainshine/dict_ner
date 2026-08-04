# HANDOVER.md v3.6.0

> 最后更新: 2026-08-04
> v3.6.0: v1.4.0 词频全量重统 (stats bootstrap 换 v3 引擎)

## v3.6.0 变更摘要

**核心**: 词频真更新。原 stats 管道硬编码 `OrgDPRecognizer(v1.1.1)` 做切分统计, 词频停留在 v1.1.1 语义。本轮用 v3 引擎 v1.3.0 重切统计源, 完成自举迭代第一轮。

**P1 stats** (`tools/org_chunk_stats_v3.py`/`poi_chunk_stats_v3.py`, 16进程):
- org 1.65亿 (12min) / poi 4000万 (4min) → `dicts/iter_v1.4.0/`

**P2 aggregate** (DICT_VERSION 环境变量支持):
- org_v1.4.0: d1=60,612 d3=20,121 d4=8,888 (烘焙含 bare互斥)
- poi_v1.4.0: d1=49,360 d3=4,727 d4=23,524
- poi_prune 重推导: 仅 8 词 (v1.3.0 的 203 词已在 v1.4.0 stats 中自洽, 闭环验证)

**P3 loc**: builder 全流程 (修 chunk 跳表头 bug) + Gaode 道路 freq≥10 (对齐 47万 传承, 101万 CSV 是 v2.2.x 重生成) + VILLAGE 清理 + prune 重推导 (36词) + NUMERIC/POI_SUB 注入。ROAD 42.4万。

**P4 brand_v1.4.0**: 新 d2 统计重训 (9.5MB)。

**P5 回归**:
- seg_compare v1.3.0→v1.4.0 全量: org 4.45% / poi 4.49% / **loc 0.98%** (LOC 收敛)
- badcase 修复 (10万样本): ORG 6.2% / POI 2.0% / LOC 0.8%
- seg_quality 不降: org addr 验证 89.2%→90.1%
- **test macro-F1 0.9061** (val 0.9064, UNKNOWN 0.9289, ORG 0.8662/POI 0.9077/ADDR 0.9215)

**关键认知**:
- v1.4.0 后词频与切分语义自洽 (poi_prune 从 203→8 即是证明), 下一轮自举 (v1.5.0) 边际收益将快速递减
- aggregate 支持 `DICT_VERSION=v1.x.y` 环境变量指定版本
- 烘焙开关 `_is_baked()`: v1.3+ 词典加载不打补丁

**测试**: 124 条全绿。

---

# 以下为 v3.5.0 存档

# HANDOVER.md v3.5.0

> 最后更新: 2026-08-04
> v3.5.0: UNKNOWN 真实样本扩充 + 词典实体化 v1.3.0 + 亿级回归 + 工程化

## v3.5.0 变更摘要

**A. 词典实体化 v1.3.0** (`tools/bake_v130_dicts.py`)
- 加载层补丁全部烘焙进 pkl: org_v1.3.0 (d1=85,771) / poi_v1.3.0 (d1=50,374, d4=23,590) / loc_v1.3.0 (POI_SUB=30, NUMERIC=20)
- configs.py `baked` 开关: v1.3.0 加载不再打运行时补丁
- 零差异门禁: 补丁引擎 vs 实体化引擎 5K 样本三体系完全一致
- **亿级全量回归** (`v3/seg_compare.py`, output/v3_seg_compare_report.md):
  - ORG 1.65亿: diff 2.67%, TOWN -271万 → POI +255万 (商店/酒店归位)
  - POI 4000万: diff 7.21%, TOWN -194万 → POI +274万
  - LOC 3635万: diff 10.24%, NUMERIC/POI_SUB 从零 → 272万段, UNKNOWN +3.6% (与拆分/数字分段的预期代价)

**B. 工程化**
- `run.py classify` 默认 v3 模型; `run.py v2 classify` 走旧规则链
- 延迟: 单条 classify 1.5s (GBDT 逐树开销) → `classify_batch` 向量化后 **26ms/条 (58×)**
- compact 模型 (150树/31叶) 留档 `models/clf_v3_compact.pkl`: 0.45s/条, 三类 F1 低 ~0.01, 仅供延迟敏感场景

**D. UNKNOWN 真实样本**
- 来源: 高德"室内设施" (会议室/桌号/摊位, 定义=非独立实体→UNKNOWN); 腾讯无"公交线编号"类别 (实为名称污染, 正则提取噪声大已放弃)
- 23K→去重 11,754 条, 60/20/20 追加进 eval splits (val/test UNKNOWN support 10/9 → 2,360/2,361)
- **test macro-F1 0.8016 → 0.9000**: UNKNOWN F1 0.9064 (P 0.97 / R 0.85), ORG 0.8658 / POI 0.9044 / ADDR 0.9235

**指标汇总** (test):

| 版本 | macro-F1 | accuracy | 说明 |
|------|:---:|:---:|------|
| v2.2.1 | 0.3702 | 0.4463 | 规则链 |
| v3.0.0 | 0.7699 | 0.9114 | GBDT 首版 |
| v3.4.0 | 0.8016 | 0.9088 | 三体系 R1 全落地 |
| v3.5.0 | **0.9000** | 0.9041 | UNKNOWN 真实样本 (support 9→2361) |

> macro-F1 大涨主因 UNKNOWN 从噪声类变成可学习类; 三类业务指标持续提升但增幅温和。评测口径变化已记录, 跨版本对比时注意 UNKNOWN support 差异。

**测试**: 124 条全绿。

## v1.3.0 系统评估 (E1+E2, 2026-08-04)

**E1 重切**: `v3/eval_cut.py` 用 v3 引擎 (baked v1.3.0) 重切三体系全量 → `output/*_eval/*_v1.3.0/` (schema 与 legacy eval 同构; legacy eval_launch 不能用于 baked 词典——legacy bare 注入规则不同会双重注入)。

**E2 结论** (`output/v1.3.0_eval_report.md`):
- badcase 修复率 (10万样本/体系): POI **18.2%** / ORG 5.5% / LOC 0.9% (+19% CHANGED_LOW 为 NUMERIC/POI_SUB 新序列长尾, 语义审查为改善)
- seq_dist: POI 低频序列种类 -28,362 (-14.5%), ORG -5,130
- 无回归项; ORG 裸名歧义与 LOC addr 覆盖假象为已知遗留

**数据血缘备忘**:
- `split/org` 1.65亿 (org_corpus.csv 历史产物, 源文件不在仓库)
- `split/poi` 4000万 (兴趣点A/T input.txt → poi_dedup.py)
- `split/loc` 3635万 (loc_corpus.csv 已删, 直接读 chunk)
- `split/org_company` 5200万纯公司名 (公司名input.txt GBK, **仅作评测集, 未并入 org stats**, 用户决策)
- 兴趣点A/T、地名A/T 与 Gaode/Tencent 同源

**磁盘治理**: output/*_eval 只保留 stats + chunk_00.jsonl (评估完成后 JSONL 按 15/16 清理, 140GB→9GB)。

**待办 (下一轮)**: v1.4.0 词频全量重统 (org/poi launch stats + aggregate + loc builder + brand 重训), 见 README v3.5.0 后续。

---

# 以下为 v3.4.0 存档

# HANDOVER.md v3.4.0

> 最后更新: 2026-08-04
> v3.4.0: POI 体系 R1 — 位置证据剪枝 (203 词 d1→d4) + bare 注入跳过 d4

## v3.4.0 变更摘要

**病灶**: POI 词典 d1 混入大量后缀词——SQL 在 poi 语料切分时把"酒店(47.9万)/商店(29.4万)/市场/公园/新村/南区/路口"等末尾后缀错标为 d1, 被 bare_name_type 推断成 TOWN。POI 体系 TOWN 未命中率高达 68.1%。

**挖掘** (`v3/poi_prune.py`): 位置证据——poi 名称中真地址词应在开头。千万级语料统计候选词 (d1 freq≥1000, TOWN 族推断) 的开头/结尾出现次数, 结尾占比≥85% 且 ≥100 次 → 203 词从 d1 移入 d4 (`dicts/poi_prune_v1.3.0.json`)。

**配套修复 (通用原则)**: bare-name 注入跳过 d4 词——否则 5000-freq 裸名 TOWN 在 Trie 碰撞中按行政优先级压掉 47 万 freq 的 d4 POI (公园/市场案例)。此修复同时根治了 ORG 侧同类残留。

**被否决的方案** (已验证勿再试):
- org bare 注入全关 → 河南/济南等裸省名退化为 ROAD, 万宝镇/豫兴路切错, 回归明显
- poi_prune 不加 TOWN 族限制 → "南路/大桥"等因嵌套后缀 (河南路⊃南路) 位置统计失真, 会误删真道路词

**效果**: POI 末段后缀率 64.7%→68.3%, 低频序列率 1.48%→1.31%。test macro-F1 **0.8016** (系列最佳), 三类 F1 0.8702/0.9141/0.9224, clean accuracy 0.9896。

**测试**: 124 条全绿。

---

# 以下为 v3.3.0 存档

# HANDOVER.md v3.3.0

> 最后更新: 2026-08-04
> v3.3.0: LOC R1 第二轮 — 伪行政词剪枝 + 道路连词拆分

## v3.3.0 变更摘要

**POI overmerge 排查结论**: 1.5% (2,981例) 几乎全是度量误报 (灯饰馆/馄饨王/兰花园是合法完整词), 不修复, 避免过度切分。

**LOC addr 验证率残差分析** (88.5%): 大部分是 addr_csv (org 语料) 对 loc 语料的覆盖假象 (办事处/自贸区/数字巷里)。两类真实病灶:

1. **伪行政词条**: "超市" CITY freq=2,866 vs POI 6.88M, Trie 碰撞优先级 (CITY<POI) 让低行政频碾压高商业频。挖掘规则: 未被 areas/ 证实 + admin freq<10000 + POI freq≥100× → 36 词 (`超市/生鲜超市/便民超市/综合门市/粮油门市...`)。产出 `dicts/loc_prune_v1.3.0.json`, 引擎加载时应用。
2. **"与X路"误并**: "工业路与解放路交叉口" 被模式匹配成整段 ROAD。新增 `_post_strip_road_conjunction` 钩子拆为 ROAD+与+ROAD。

**效果**: addr 验证率 88.5%→88.9%; test ORG/POI/ADDR F1 0.8684/0.9134/0.9247 (持平); macro-F1 0.7838 (UNKNOWN n=9 噪声所致, **以三类 F1 为准**)。

**经验沉淀**: 段健康度指标会饱和, 后续迭代以"门禁 diff 逐类审查 + 分类三类 F1 + clean accuracy"为验收三角。

**测试**: 124 条全绿。

---

# 以下为 v3.2.0 存档

# HANDOVER.md v3.2.0

> 最后更新: 2026-08-04
> v3.2.0: LOC 体系 R1 — NUMERIC/POI_SUB 从零建模
> 详见 audit/v4.0_d0_findings.md

## v3.2.0 变更摘要 (LOC R1)

**病灶**: LOC 词典 `NUMERIC`/`POI_SUB` 两类**完全为空** (转移表里有规则但词典无词条)。后果: "人民路88号"→3个UNKNOWN单字, "瓦房村3组"→VILLAGE+3个UNKNOWN, 楼层/门牌/村组全部落入 UNKNOWN (unknown_char_rate 4.0%, 占 LOC 残差的~80%)。

**修复** (`v3/engine/configs.py`, 加载层注入, 不改 pkl):
- NUMERIC: 0-9 + 全角数字 (freq=5000), 链式 (NUMERIC,NUMERIC)=1.0 原有
- POI_SUB: 号/层/楼/栋/幢/单元/室/组/队/排/间 + 一层~十层/一楼~十楼/负一层/负一楼 (24词, freq=80)
- 转移表增量 (9条, `LOC_EXTRA_TRANSITIONS`): NUMERIC→POI_SUB 0.2, VILLAGE/COMMUNITY→NUMERIC 0.5, POI→NUMERIC 0.5 等
- dp.py `merge_same_type` 增加 NUMERIC 合并 ("88"合成一段)

**效果**:
- "人民路88号"→ROAD+NUMERIC+POI_SUB, "瓦房村3组"→VILLAGE+NUMERIC+POI_SUB, "前海西街12号楼"→ROAD+NUMERIC+POI_SUB(号楼合并)
- LOC diff 7.1% (3000样本), 逐类审查**均为改善**
- unknown_char_rate 4.02%→3.42%
- low_freq_seq 12.3%→14.7% 为**指标假象** (新正确序列初始稀有, 非回归)
- test macro-F1 0.7913→**0.8009**, val clean accuracy 0.9903

**段健康度基线汇总** (20万样本/体系, `v3/seg_quality.py`):

| 体系 | 末段后缀率 | 后缀验证 | 行业验证 | 地址验证 | unknown率 |
|------|:---:|:---:|:---:|:---:|:---:|
| ORG (R1后) | 97.65% | 97.87% | 99.28% | 89.15% | — |
| POI | 64.74% | 97.64% | 100% | 57.3%* | — |
| LOC (R1后) | — | — | — | 88.49% | 3.42% |

> *POI 地址验证率低主要是 addr_csv 对 POI 语料小镇覆盖不足 (覆盖假象), 非切分错误。

**测试**: 124 条全绿。

---

# 以下为 v3.1.0 存档

# HANDOVER.md v3.1.0

> 最后更新: 2026-08-04
> v3.1.0: 分类器优化 (清洗二轮+UNKNOWN增广+clean评测) + R1 词典修复 (bare-name 商业后缀)
> R2 按预案回退, 详见 audit/v4.0_d0_findings.md

## v3.1.0 变更摘要

**分类器 (v3.0→v3.1)**:
1. 标签清洗二轮: 类条件阈值 (ORG/POI 0.55, ADDR 0.65) + 高置信矛盾**翻转标签** (P≥0.9, 35,172 条翻转 + 179,120 条剔除)
2. UNKNOWN 合成增广: `v3/synth_unknown.py` 5 万条 (英文/数字/单字/乱序/符号)
3. clean 评测子集: `v3/clean_eval.py` 模型无关查表信号确认标签 (val/test 各 ~31%), 双指标报告
4. **关键认知**: clean 子集 accuracy 0.9919 — 模型在可信标签上近完美; 原始标签 macro-F1 ~0.79 的"错误"大部分是评测集标签噪声

**R1 词典修复 (加载层, 不改 pkl)**:
- 病灶: `bare_name` 注入 (areas 镇/村裸名, freq=5000) 把"商店/酒店"注入成 TOWN, 且 UNKNOWN→addr 转移 0.0 比 UNKNOWN→POI 0.2 便宜, 压倒了 d4=189万 的"商店"
- 修复: `v3/engine/configs.py` bare 注入跳过 SQL 主导商业后缀 (条件: suffix_csv org≥10000 且 org≥10×loc, 命中 38 词: 商店/酒店/商城/山庄/金店/猪场/茶坊…)
- 门禁: org diff 1.5% / poi diff 1.1% (审查样例**几乎全是改善**: 商店 TOWN→POI, 酒+店→酒店, 分中心 TOWN→POI)
- 段健康度 (20万 org 语料): 末段 ORG_SUFFIX 率 96.84%→97.65%, 地址验证率 88.5%→89.2%, 低频序列率 5.29%→5.17%
- 词典改动后全链路重跑: 特征重预计算 → 清洗重跑 → 分类器重训 (~15min, 管线自动化)

**R2 回退决策**: D0 调研确认全文本金标准切分不存在 (split tag 列是 0/1 标记, 地名input 是纯名称), 银标准目标函数过弱, 按预案只做 R1。见 `audit/v4.0_d0_findings.md`。

**指标** (36K test):

| 指标 | v3.1.0 | v3.0.0 | v2.2.1 |
|------|:---:|:---:|:---:|
| macro-F1 (原始标签) | 0.7913 | 0.7699 | 0.3702 |
| macro-F1 (clean子集) | 0.8941 | — | — |
| accuracy | 0.9084 | 0.9114 | 0.4463 |
| accuracy (clean子集) | 0.9919 | — | — |

> UNKNOWN 类 support 极小 (test n=9), F1 逐次波动 0.36~0.57 属噪声, 以 clean accuracy 为准。

**测试**: 124 条全绿。

---

# 以下为 v3.0.0 存档

# HANDOVER.md v3.0.0

> 最后更新: 2026-08-04
> v3.0.0: 分类层学习化重构 (GBDT+confident learning) + 统一 DP 引擎, v2.2.1 冻结为 baseline
> 详见 `audit/v3.0_refactor_plan.md`

## v3.0.0 变更摘要

**诊断**: v2.x 是规则补丁链 (~20 个手调魔法数), score 量纲不一致导致 ADDR→UNKNOWN 误吞 2.6 万条; 评测标签 (Gaode type 机械映射) 有噪但从未用于"学"。

**方案**:
1. **评测基座**: eval_set 180K → train/val/test 60/20/20 分层固定切分 (种子42, `data/eval_split_*.csv`)
2. **特征**: `v3/features.py` 78 维 (段级/查表/统计/规则信号), 训练推理同一代码路径
3. **大语料**: `v3/sample_pool.py` Gaode 2M + Tencent 1M 弱标注采样 (剔除 val/test 文本防泄漏) → 270 万
4. **标签清洗**: `v3/labels.py` 3-fold CV confident learning, 高置信矛盾剔除 14.6 万 (5.4%), 噪声率报告 `output/v3_noise_report.md`
5. **训练**: `v3/train.py` HistGradientBoosting (500 iter) + FrozenEstimator isotonic 校准 + val 集类别乘数标定 → `models/clf_v3.pkl` + manifest
6. **统一 DP 引擎**: `v3/engine/` (dp.py + configs.py), LOC/ORG/POI 三套配置, 与旧识别器 **20K 样本零差异** (`v3/engine/gate.py` 门禁)
7. **推理**: `v3/infer.py` V3Classifier 契约兼容; `run.py v3 classify` (默认入口仍为 v2)

**指标** (36K test, 一次性):

| 指标 | v3.0.0 | v2.2.1 | Delta |
|------|:---:|:---:|:---:|
| macro-F1 | 0.7699 | 0.3702 | +0.3997 |
| accuracy | 0.9114 | 0.4463 | +0.4651 |
| ORG F1 | 0.8756 | 0.5203 | +0.3553 |
| POI F1 | 0.9154 | 0.5419 | +0.3735 |
| ADDR F1 | 0.9250 | 0.4163 | +0.5087 |

val macro-F1 0.8219。UNKNOWN support 极小 (test n=9), F1 波动大属正常。

**已知边界**: "星巴克咖啡望京店" → ADDR (0.51 vs POI 0.48), "望京" 在评测集中多标 ADDR 所致, 真实边界样本。

**治理**: 分类层改动须 val macro-F1 不降; 段识别改动须过 `v3/engine/gate.py` (diff <0.5%); 模型产物必带 manifest。

---

# 以下为 v2.2.1 存档

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
