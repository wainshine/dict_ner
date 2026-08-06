# HANDOVER.md v4.1.0

> 接手手册：架构 / 管线 / 数据血缘 / 门禁 / 决策记录 / 踩坑。
> 版本历史见根目录 `CHANGELOG.md`；项目门面见 `README.md`。

## 0. 当前状态速览

- 系统版本: **v4.1.0** | 词典: **v1.5.0**（loc/org/poi/brand 四词典统一编号）
- 测试: **184 条全绿** (`python3 -m unittest discover -s tests/`；tests/legacy/ 71 条 + 根目录 113 条)
- 关键指标: test macro-F1 **0.9092** (v4.0.4 标签治理后口径) | clean 子集 accuracy 0.9919 | 置信度 ECE 0.0149 | 单条延迟 2.1ms / 批量 1.9ms/条 (v4.0.3)
- 段健康度: org 后缀验证 97.9% / addr 验证 98.6% / 低频序列 4.4%
- v4.0.0 布局: v2 冻结代码平铺于 `/v2/`（识别器/brand/eval + v2/tools/），v2 总线 = 根 `pipeline_v2.py`，legacy 测试在 `tests/legacy/`；HTTP 服务 = `serve.py`（FastAPI）
- **v4.0.0 起 v3 不再 import 任何 v2 模块**（`v3/pipeline.py` 自包含；`classify_suffix` 在 `core/suffix_classify.py`）；仅 gate/seg_compare/badcase_eval 保留 legacy 基线对比 import（`v2.*`，属预期）

## 文档定位与维护原则

| 文档 | 定位 | 更新时机 |
|------|------|---------|
| `README.md` | 门面: 是什么/怎么用/效果多少 | 每次发版同步 |
| `audit/HANDOVER.md`（本文件） | 接手手册: 架构/管线/血缘/门禁/决策/踩坑 | 每次发版同步 |
| `CHANGELOG.md` | 版本历史唯一来源 | 每次发版新增一节 |

维护原则：
1. **单一来源**：版本历史只写 CHANGELOG；架构/流程/决策/踩坑只写 HANDOVER；README 放简版+链接。
2. **发版三件套**：改代码发版 = 代码 + 三文档 + git 提交，一次完成，不留文档债。
3. **版本号一致**：三文档头部版本号与 `run.py VERSION`、`core/config.py VERSION` 保持一致；词典任一变更四词典版本号同升（统一版本政策）。

## 1. 系统框架

### 1.1 四层架构

```
输入文本
  │
  ├─ L1 切分层: v3/engine/ 统一 Viterbi DP 引擎
  │     一个引擎类 (DPEngine) + 三套 EngineConfig (loc/org/poi)
  │     组件: Trie (碰撞=行政优先级) / 转移代价表 / 词成本(IDF+长度惩罚) /
  │           单字兜底路径 / 后处理钩子链
  │
  ├─ L2 总线层: v3/pipeline.py V3Pipeline
  │     后处理: POI→ORG_SUFFIX remap / _merge_over_split 过度拆分合并 /
  │             _detect_compound 复合机构检测重识别 / 查表 (d4_map/suffix_table/sql_suffixes)
  │
  ├─ L3 特征层: v3/features.py 78 维
  │     段级 (各 SegType 计数/覆盖率/末段类型) / 查表 (d4_map 类别 one-hot/
  │     suffix_table/sql 亲和度) / 统计 (长度/数字/英文/brand_score) /
  │     规则信号 (has_comp/has_gov/double_negative)
  │
  └─ L4 分类层: models/clf_v3.pkl
        HistGradientBoosting (500树×4类) + isotonic 校准 (FrozenEstimator on eval_train)
        + 类别乘数 (val 标定) + 拒绝阈值 → UNKNOWN
        v3/fast_predict.py: 编译化推理 (numpy 树遍历), 与 sklearn 零误差
```

### 1.2 统一 DP 引擎 (v3/engine/)

| 组件 | 说明 |
|------|------|
| Trie 构建 | `build_trie(entries)`: 碰撞时 LEVEL_ORDER 行政优先级高者胜, 同级取高频 |
| 转移代价表 | 每体系一张; org: d4 终点约束; loc: 行政层级链; poi: 允许相邻 d4 |
| 词成本 | IDF(-log((f+1)/(total+1))) + 长度惩罚 (1字+1.5, 2字+0.5, >8字+0.3/字), 下限 0.5 |
| 单字兜底 | org=UNKNOWN(2.0) / loc=CHAR(3.0, 跳标点) |
| 短 d4 惩罚 | org: 2-3 字 d4 freq<50K 且非近末尾 → 成本抬至 7.0 |
| 后处理钩子 | 见 1.3 |

### 1.3 后处理钩子链 (org 引擎为例)

```
assign_poi_types → merge_unknown (连续未识别合并) → trailing_single (末尾单字归并)
→ leading_bracket (「（」并入后续后缀段) → relabel_brand (UNKNOWN→BRAND)
→ adjudicate_town (bare TOWN 中部位+后接 INDUSTRY/POI → BRAND, 镇村合并/政府后缀保护)
```

loc 引擎钩子: merge_orientation / strip_road_conjunction ("与X路"拆分) / merge_location / merge_same_type / assign_poi_types_loc。

### 1.4 分类器

- 训练: GBDT (max_iter=500, lr=0.08, leaves=63, l2=1.0) on 268 万样本 → CalibratedClassifierCV(FrozenEstimator, isotonic) 校准集=eval_train → 类别乘数+拒绝阈值在 val 按 macro-F1 标定
- FastGBDT 原理: sklearn 逐树 Python 调用慢 (0.7ms×2000), 编译化为 numpy 数组批量遍历; **注意 sklearn 节点值已含 learning_rate (lr=1.0)**; 叶掩码防止提前到叶的行弹回根节点; **v4.0.3 树间批量化**: 全部树 padding 统一节点数, (n_rows × n_trees) 同步遍历, 单条 50ms→2.1ms
- 置信度: isotonic 校准, ECE=0.0129, 可直接作概率路由

## 2. 训练与词典管线

### 2.1 分类器训练全链

```
v3/sample_pool.py     Gaode 2M + Tencent 1M 弱标注采样 (按 type 分布, 剔 val/test 文本防泄漏)
                      → data/v3_train_pool.csv (270万)
                      ⚠️ v4.1.0 起原始语料已删 (异地备份): sample_pool/sample_unknown/
                      build_eval_set/scripts/* 重跑需先恢复备份; 衍生产物均在库可直接用
v3/precompute.py all  16进程特征预计算 → output/v3_feat/pool_feats.csv
v3/labels.py          3-fold CV confident learning (--drop-org 0.55 --drop-poi 0.55
                      --drop-addr 0.65 --flip 0.9) → pool_feats_clean2.csv
合并: clean池 + synth UNKNOWN 5万 + eval_split_train → final_train3.csv; v4.0.4 标签治理补丁版 = final_train6.csv (当前训练输入)
v3/train.py           GBDT + FrozenEstimator isotonic (校准集=train_feats) + val 标定
                      → models/clf_v3.pkl + manifest_v3.json + val_pred.csv
```

### 2.2 词典构建链 (v1.5.0)

```
1. stats 重切: STATS_VERSION=v1.4.3 python3 tools/stats_launch_v3.py
   (org/poi_chunk_stats_v3.py, 用上一版引擎切分语料统计 d1/d2/d3/d4 词频)
2. aggregate: DICT_VERSION=v1.5.0 python3 tools/org_aggregate.py / poi_aggregate.py
   (剪枝 d1≥5/d3≥3/d4≥100 + loc>org 质量过滤 + split_polluted_d4 + gov seed + POI_EXCLUDE)
3. 补丁固化 (每轮 stats 后必须重跑):
   v3/poi_prune.py --dict poi_v1.5.0.pkl  (位置证据 d1→d4)
   tools/patch_v141.py --src-v v1.5.0 --dst-v v1.5.0  (括号归一化/误杀回补/数字垃圾/d1冲突)
   tools/patch_v142.py --src-v v1.5.0 --dst-v v1.5.0  (村委会复合词/d3<10)
   bake: v3.engine.configs._load_org_dicts(baked=False) 快照 (bare 注入互斥)
4. loc: tools/loc_build_v140.py (builder全流程) → merge_gaode_roads (freq≥10)
   → clean_loc_villages → loc_prune 重跑 + NUMERIC/POI_SUB 注入
5. brand: train_from_d2_csv(iter_v1.5.0/org_d2_freqs_v1.5.0.csv)
```

### 2.3 stats 自举机制与收敛判断

stats 用 v(N-1) 引擎切分语料统计词频 → 产出 vN 词典 → 切分又变 → 自举迭代。
收敛证据（v1.4.0→v1.5.0）：poi_prune 词数 203→8；村委会复合词新增 0；seg diff 主要来自 BRAND 碎片合并改善。**判断：已收敛，不建议 v1.6 再自举**（收益进入噪声带）。

### 2.4 统一版本号政策

任一词典变更，loc/org/poi/brand 四个 pkl 版本号一起升（未变的做内容拷贝）。当前 v1.5.0。保留：v1.2.x（v2 baseline + legacy 测试锚定）、v1.1.x（兜底，不可删）。

## 3. 数据血缘

### 3.1 原始数据

| 数据 | 规模 | 状态 |
|------|------|------|
| `data/高德amap/` | 67 文件 11GB GBK 6450万行 | **已删 (v4.1.0 磁盘治理, 有异地备份)**; 衍生产物 eval_set/pool/splits 全留存 |
| `data/腾讯地图/` | 345 文件 7.5GB GBK 7200万行 | **已删 (同上)** |
| `兴趣点A(6500w)/T(7200w) input.txt` | GBK 纯名称 | 已删 (更早期清理) |
| `地名A(7300w)/T(7200w) input.txt` | GBK 纯名称 | **已删 (v4.1.0)**; 副作用: `v2/eval.py` (冻结 LOC 采样评估器) 失效, v2 classify 运行时不受影响 |
| `公司名input.txt` | GBK 5200万公司名 | 已删 (更早期清理); split/org_company 留存 |
| `org_corpus.csv` | — | **不存在**（split/org chunks 是历史产物） |
| `loc_corpus.csv` | — | **已删**（split/loc chunks 留存） |

### 3.2 split 语料（训练/统计的唯一来源）

| 目录 | 格式 | 规模 | 来源 | 用途 |
|------|------|-----:|------|------|
| `split/org/` | `dict,poi,idf,tag,ner,moe` | 1.65亿 | org_corpus（历史） | org 词典统计/挖掘/评估 |
| `split/poi/` | `name\tfreq` TSV | 4000万 | 兴趣点A/T → poi_dedup.py | poi 词典统计/纯净集 |
| `split/loc/` | `dict,idf` | 3635万 | loc 语料（loc36kw） | loc 词典/评估 |
| `split/org_company/` | 纯文本一行一名 | 5200万 | 公司名input.txt | **仅评测**（用户决策） |

### 3.3 SQL 三表角色变迁

`addr/trade/suffix_segments_sql.csv`（d1/d3/d4, 200万/4万/2.4万）：v1 时代是词典本体 → 现为**验证层**（aggregate 质量过滤、csv_index 亲和度特征、误杀回补依据、bare 互斥判定）。注意 `org_ratio` 衡量语料频率非实体类型，不能单独分 ORG/POI。

### 3.4 其他数据资产

- `data/areas/` 五级区划（省32/市343/区县2979/街道41353/村620574）：loc 词典 + bare 注入 + prune 证实
- `data/gov_suffix_seed.csv` 29 条 / `data/suffix_seed.csv` 2.4 万条：种子注入
- `dicts/d4_category_map.pkl` 8,299 条 / `dicts/suffix_category_gaode.csv` 1,520 条：Gaode 标注（特征+回补依据）
- `data/eval_set.csv` 18万 → `eval_split_{train,val,test}.csv`（+室内设施 UNKNOWN 扩充后 11.6万/3.85万/3.85万）

## 4. 评测体系与门禁

### 4.1 三视角指标

| 视角 | 工具 | 当前值 |
|------|------|-------:|
| 含噪标签 macro-F1 | `v3/evaluate.py` | test 0.9092 (v4.0.4 标签治理后口径; 旧口径 0.9059) |
| clean 子集 accuracy | `v3/clean_eval.py` | 0.9919（查表确认标签, ~31% 子集） |
| 纯净集召回 | `v3/pure_eval.py` | ORG 74.4% / POI 58.3%（语义边界, 详见报告解读） |
| 有效召回 (真边界剔除) | `v3/pure_eval.py report` 分层口径 | POI **84.0~85.8%** / ORG ≈100%（v4.0.1 新增, 规则见 v3/poi_recall_audit.py） |
| 置信度 | `v3/calibration_audit.py` | ECE 0.0129 |

### 4.2 段级门禁

| 门禁 | 工具 | 标准 |
|------|------|------|
| 引擎一致性 | `v3/engine/gate.py` | 实体化/重构后新旧零差异。**注意 (v4.0.0 核实)**: 当前词典 v1.5.0 下 gate 对比 legacy 识别器（锚定 v1.2.x 词典）必然 FAIL (20K diff loc 1943/org 1753/poi 2604)，属词典代差非引擎问题；重构类变更的验收标准是 diff 计数与变更前逐项一致 |
| 段健康度 | `v3/seg_quality.py` | 后缀/行业/地址验证率不降 |
| 全量段对比 | `v3/seg_compare.py` | diff 率 + 类型迁移逐类审查 |
| badcase 修复率 | `v3/badcase_eval.py` | REPAIRED 提升无回归 |
| eval 重切 | `v3/eval_cut.py` | 产出 output/*_eval/*_vX/ JSONL+stats |

### 4.3 磁盘治理

- `output/*_eval/` v4.1.0 起整目录清除（JSONL 13.4G + stats.json 656MB 全删，只留 3 个 `*_eval_report.md` 于 output/ 根；可再生：`v3/eval_cut.py run <system>` 从 split/ 重切）
- `output/v3_feat/chunks|feats` 临时分片可删；只留现役 `final_train6.csv` + `train/val/test_feats.csv`（pool_feats/final_train3 等历史特征文件 v4.1.0 已清，可由 `data/v3_train_pool.csv` 重算再生）
- `dicts/iter_vX/` 只留最新一代（现役 iter_v1.5.0；iter_v1.2.x v4.1.0 已清，iter_v1.6.0 实验结束后已清）
- v4.1.0 大清理 (~42GB)：原始语料（高德/腾讯/地名 input）删除有异地备份；v2 评测快照 json 删除；被否实验模型一律不留（数字记档即可）

## 5. 治理规则（红线）

1. v2 模组（`/v2/` + 根 `pipeline_v2.py`，v4.0.0 迁移后）冻结为 baseline，只读不改
2. 词典不覆盖旧版；v1.1.x 兜底不可删
3. 词典改动 → 四词典版本号同升 + seg_quality 不降 + 分类器重训
4. 引擎改动 → gate 零差异门禁（或 diff 逐类审查为改善）
5. 分类器改动 → val macro-F1 不降 + manifest 更新
6. 发版 = 代码 + README/HANDOVER/CHANGELOG 三件套 + git 提交

## 6. 已知遗留与决策记录

| 事项 | 决策 | 理由 |
|------|------|------|
| 裸名歧义残留 (幸福/鑫源类中部位品牌词) | 暂缓, 分类器兜底 | 真镇名 vs 品牌词, 位置证据不可分; v4.1.0 seq_anomaly 量化: org 6.8%/poi 4.2%/loc 12.3% (段级), 分类指标不受影响; 修复候选 (尾部 bare 约束钩子) 留档 output/v4_seq_anomaly.md |
| demote_bare_admin 段美化钩子 | **回退 (v4.1.0)** | 行政后置降级钩子段级效果显著 (org R2 -71%, low_freq_seq 4.4%→3.5%) 但分类器特征漂移: 不重训 -1.5pt / 重训 val 0.9047<0.9091。**段美观与分类指标不可兼得——组织段的行政信息被分类器有效利用 (分公司城市名等)。三次修复实验 (A一期/二期/demote) 同结论: val 门禁是硬约束, 段级问题分类器兜底的架构是有效的** |
| 结构 badcase 清洗 (seq 单例/≥13段) | **不采纳 (v4.1.0)** | 训练池 1.21% (32,633 条) 结构可疑行剔除重训: val 0.9086<0.9091, test 持平 0.9092 → 结构噪声对分类器无可见收益 (GBDT 鲁棒 + CL 已洗标签)。badcase 清单留档 output/v4_train_badcase.csv 可用作切分质量审计样本源 |
| R2 转移代价学习 | 回退 | D0 调研确认全文本金标准不存在 (audit/v4.0_d0_findings.md) |
| LOC 村委会复合词 (VILLAGE 25.4万) | **保留** | 地址语境中"XX村委会"指地点; ORG 语境才是机构 (v1.4.2 已删 ORG 侧) |
| org_company 5200万 | 仅作评测集 | 用户决策, 不并入 org stats |
| 室内设施/公交线 | = UNKNOWN | 非独立实体定义 (用户决策) |
| gaode_roads.csv 101万行 | merge 时 freq≥10 过滤 | 对齐 47万传承; 该文件是 v2.2.x 以 freq≥3 重生成 |
| 评测集标签噪声 ~13% | 程序清洗 + clean 子集双指标, 不人工修 | 用户决策 |
| v1.6 自举 | 不做 | 已收敛 (v3.9.0 判断) |
| POI 召回攻坚 D1-A 增强重训 | **回退** | 24K 真错误模式 POI 样本增强 (v3/augment_poi.py → final_train4) 重训后 val macro-F1 持平 (0.9050 vs 0.9052), 但 12 条真错误点查 0 翻转——残存误判是特征驱动 (专名含地名→geo_cov 抬升 + eval 标签 寺/景区→ADDR 倒挂), 非标签量不足。模型 artifacts 留存 models/clf_v3_poi.pkl 备查, baseline 不换 (v4.0.2) |
| A 二期强 POI 后缀特征 | **回退** | d4_strong_poi/poi_d4_strong_poi 特征 (80维) 重训: val 0.9035 < 0.9052 未过门禁 + 0/12 翻转。eval 标签在后缀上倒挂, 加显式特征反而撞 test 噪声。features.py 回滚 78 维 (v4.0.3) |
| macro-F1 提升路径 | 评测集标签治理, 非模型调参 | P2 逐类诊断: 四大迁移类 87% 是标签噪声+体系边界; 含噪口径可修复空间仅 ~1-2pt (v4_f1_error_audit.md) |
| eval 标签治理 | **采纳 (v4.0.4)** | 两条错误映射修正 (tencent休闲娱乐→POI; gaode风景名胜点位后缀→POI), 三 split 1,846 条 + pool 13,126 条, `.bak_v1` 备份; 重训 val +0.0037 过门禁, baseline 更换 (旧模型归档 clf_v3_baseline_v39.pkl) |
| eval 集重建注意 | splits 无 type_orig 列 | type_orig 只在 eval_set.csv/feats CSV; 关联用 text join; UNKNOWN 扩充行 (室内设施) 不在 eval_set, join 会 miss ~7K 属正常 |
| 标签治理二轮 | **不动 (v4.0.5)** | gaode商务住宅/tencent建筑房产→ADDR 样本审查正确 (小区/楼栋); 公司企业→ORG 个体户残留无 t2 可分, 属体系边界。eval 标签治理收敛 |
| v1.6.0 词典自举 | **回退留档 (v4.1.0)** | 推翻 v3.9.0 不做决策执行全链验证: stats 重切→bake→四词典产出; seg_quality 持平但 seg_compare org BRAND 碎化 (+6.5K/20万); 重训 val 0.9056 < 0.9091 未过门禁 → 生产保持 v1.5.0。**结论: v3.9.0 收敛判断正确, 自举正式关闭**。artifacts: dicts/*v1.6.0.pkl + models/clf_v3_v160.pkl + dicts/iter_v1.6.0/ |
| POI 纯净召回口径 | 分层化 | 57.5% = 与地图源标注一致率; 真边界 (机关/交叉口/楼栋门牌/自然地名) 剔除后有效召回 84.0~85.8% (v4_poi_recall_audit.md) |

## 7. 踩过的坑

**v1 时代**：
1. **macOS spawn 模式**: Pool 子进程必须独立 .py + `__name__` 包裹, 最稳方案是 bash `&` 16 进程后台
2. **d444 temp 字段**: 不是质量分, 是 SQL 处理阶段标记, 不要用来过滤
3. **体系循环**: loc/org/poi 三个系统的后缀词典各自演化, 互不混用
4. **d111 注入**: 只能 fallback 时用, POI 用 dict_name 独立加载后必须跳过
5. **POI dict_name vs version**: poi_chunk_stats.py 必须传 dict_name 而非 version, 否则加载 org 词典
6. **suffix_segments_sql.csv 无法区分 ORG/POI**: org_ratio 衡量语料出现频率而非实体类型
7. **道路名复合名**: "药王路与香山路"需拆分统计
8. **单字符后缀缺失**: "店""馆"不在 SQL CSV (d4 要求 len≥2), 需手动补入
9. **csv.field_size_limit**: 3 个 Gaode 文件超默认限制, 需设 100MB
10. **Gaode 单文件 type 分布偏移**: 不能按文件均分采样, 需先扫描全量 type 分布再按比例采样

**v2 时代**：
11. **d4∉SQL CSV → POI 规则**: "XX黄河路店"中"店"不在 SQL CSV → 地址信息嵌入名称 → 一定 POI
12. **addr_affinity 的 loc_ratio 不能作 addr_score 基础分**: 短地址前缀在 org 语料高频 ("深圳市" loc_ratio=0.00), 只能 boost
13. **gov seed 注入用 max 而非 not in**: 13 个已有但低频的 gov 后缀需提升到 50000

**v3 时代**：
14. **sklearn HistGBDT 单条预测极慢**: 2000 树逐树 Python 调用 (~0.7ms×2000), 批量也按树计; 解法是 fast_predict.py 编译化。**节点值已含 learning_rate, 勿重复乘**
15. **树遍历叶掩码**: 提前到叶子的行继续循环会被 left/right=0 弹回根节点
16. **eval split 追加 UNKNOWN 后**: split 文件已含新增行, 特征文件再追加会重复计数
17. **`open(p,'w').write(open(p).read())`**: 先截断后读取 → 文件清空 (config.py 中招, git 恢复)
18. **F2 误杀回补范围**: 初版未限"仅 loc>org 误杀"导致 2,051 条过度回补, 必须 loc>org 且 org≥5000 且 ratio<15
19. **F3 数字清理白名单**: 4S店/2元店/1号店是合法后缀, 不能一刀切
20. **多进程 + OpenMP 过订阅**: 16 进程 × numpy 多线程互相拖慢 (47min 假象), 测量延迟前先杀干净后台 worker
21. **bare 注入 vs d4 的 Trie 碰撞**: 5000-freq 裸名 TOWN 按行政优先级压掉 47 万 freq 的 d4 POI — bare 注入必须跳过 d4 词
22. **聚合器 d4 质量规则误杀复合后缀**: 广场/商场 loc>org 被杀 → "广/商"裸奔碎片, 需白名单回补

**v4 时代**：
23. **迁移后的 import 漏检**: grep 只查了 `from loc./org./pipeline` 形态, 漏了 `from tools.eval_classify import` (被迁文件中的共享函数) — v3/train.py 重训时才炸。教训: 迁移后验收必须包含"全仓 py 文件 import 可解析性"检查, 不能只跑 tests (tests 不覆盖 train.py)
24. **train.py 会覆盖 val_pred.csv**: 实验性重训 (--model 指向新文件) 也会覆盖 output/v3_feat/val_pred.csv, baseline 产物需事后用 baseline 模型重算恢复
25. **POI 增强重训不翻转的原因**: 真错误是特征驱动 (geo_cov/d4 后缀倾向), 不是标签量不足; 0.9% 占比的增强样本推不动特征信号; 且 eval 标签本身倒挂 (寺 190 ADDR:52 POI)
26. **fast_predict 逐树遍历才是真瓶颈**: v3.8.0 编译化后单条仍 50ms——逐树循环本身 (2000 树 × 25 次 numpy 小数组调用) 占 98%; 树间批量化 ((n×T) 同步遍历, padding 统一节点数) 后 2.1ms。教训: numpy 小数组调用开销 ~3µs/次, 循环 5 万次比纯 Python 还慢
27. **实验重训必护 val_pred.csv**: train.py 无条件覆盖 output/v3_feat/val_pred.csv; A 一期/二期两次踩中, 均用 baseline 模型重算恢复 (v3/train.py 见踩坑 #24 同类)
28. **引擎改动必须同步重训验证**: demote 钩子只改段类型, 不重训直接 -1.5pt (特征分布漂移)——任何引擎/段行为变更, 评估必须走"重算特征+重训+val 门禁"全链, 不能拿旧模型测新特征下结论也不能拿新特征配旧模型上线
29. **bare 碰撞词不一定是 bare 注入**: 低频排行榜显示惠民/石屏/古城等碰撞词是真实区县名 (d1 真实词频), freq==5000 注入标记识别不到; 位置 (非头部/行政后置) 才是可靠判据——但位置判据又误伤分公司城市名 (见决策记录 demote 回退)

## 8. 重建速查（从零到当前版）

```bash
# 环境
pip install -r requirements.txt

# 词典 (v1.5.0 链, 详见 §2.2)
STATS_VERSION=v1.4.3 python3 tools/stats_launch_v3.py
DICT_VERSION=v1.5.0 python3 tools/org_aggregate.py && DICT_VERSION=v1.5.0 python3 tools/poi_aggregate.py
python3 v3/poi_prune.py --dict poi_v1.5.0.pkl --out dicts/poi_prune_v1.5.0.json --chunks 4
python3 tools/patch_v141.py --src-v v1.5.0 --dst-v v1.5.0
python3 tools/patch_v142.py --src-v v1.5.0 --dst-v v1.5.0
# loc/brand 见 §2.2 第 4/5 步

# 分类器 (详见 §2.1)
# ⚠️ 首行 sample_pool/sample_unknown 需原始地图语料 (v4.1.0 已删, 从异地备份恢复后重跑);
#    跳过采样直接用库内 data/v3_train_pool.csv + eval splits 即可
python3 v3/sample_pool.py && python3 v3/synth_unknown.py && python3 v3/sample_unknown.py
python3 v3/make_split.py
python3 v3/precompute.py all <输入> <输出>   # ×6 (pool/train/val/test/unknown_*)
python3 v3/labels.py --pool output/v3_feat/pool_feats.csv --drop-org 0.55 --drop-poi 0.55 --drop-addr 0.65 --flip 0.9
python3 v3/train.py --train output/v3_feat/final_train6.csv --calib-set output/v3_feat/train_feats.csv

# 门禁 (详见 §4.2)
python3 v3/engine/gate.py --n 20000
python3 v3/seg_quality.py --engine org --n 200000 --v3
python3 v3/evaluate.py --feats output/v3_feat/test_feats.csv
python3 -m unittest discover -s tests/
```
