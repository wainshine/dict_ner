# CHANGELOG

> dict_ner 完整版本历史。文档分工见 README.md「文档体系」一节。
> 系统版本 (vX.Y.Z) 指代码+算法版本; 词典版本 (v1.x.y) 指词典数据版本, v3.8.0 起四词典统一编号。

## v4.0.4 (2026-08-05) — eval 标签治理 + 重训采纳 (test 0.9062→0.9092 同口径)

P2 诊断指出的唯一提升路径落地。词典未动；**eval 三 split 标签修正（基准变更，双口径留档）**。

- **标签治理** (`v3/fix_eval_labels.py`): 修正 build_eval_set 两条错误映射——(tencent,休闲娱乐)→ADDR 实为门店 POI (足疗/洗浴/茶庄)；(gaode,风景名胜)→ADDR 中寺/庙/公园/景区点位后缀实为 POI (自然地名保持 ADDR)。三 split 共修正 **1,846 条** (train 1128/val 381/test 369)，pool 侧同规则补丁 13,126 条；原 split 备份 `.bak_v1`，明细 output/v4_eval_label_fix.json
- **重训采纳**: final_train6 (标签修正版) 重训 → **val macro-F1 0.9054→0.9091 (+0.0037，同口径过门禁)**, **test 0.9062→0.9092 (+0.003)**; ECE 0.0149 (<0.05 合格); baseline 更换为 clf_v3.pkl (tag v4.0-labelfix-v1.5.0)，旧模型归档 clf_v3_baseline_v39.pkl
- 真错误点查: 12 条翻转 1 (奇彩网吧); 公园/寺/大厦类纯语料样本仍 ADDR——它们的训练信号不在 eval 链上，受倒挂监督消除的间接收益有限
- **口径说明**: 旧口径 test macro-F1 0.9059 (v3.9.0 以来) 与 新口径 0.9092 的差含标签修正本身 (+0.0003, baseline@新标签 0.9062); 真实模型增益 +0.003

## v4.0.3 (2026-08-05) — 单条延迟 25× + macro-F1 逐类诊断 (A 二期回退)

无算法/词典变更（A 二期特征实验回退, baseline clf_v3.pkl 不换）。

- **单条延迟 50ms → 2.1ms (25×)**: profile 定位 98% 耗时在 `fast_predict.decision_function` 逐树遍历 (2000 树 × 25 次 numpy 调用); 修复为树间批量化——全部树 padding 到统一节点数, (n_rows × n_trees) 同步遍历, numpy 调用 ~25×2000 → ~25×max_depth。与 sklearn 零误差对拍 (test_fast_predict 3 条)。serve 压测: 单 worker c=1 16→103 req/s, c=4 10→292 req/s (并发不再反噬)。批量 1.9ms/条持平
- **P2 macro-F1 逐类诊断**（`v3/error_audit.py` → output/v4_f1_error_audit.md）: 四大迁移类 (POI→ADDR 1066 / ORG→POI 873 / POI→ORG 618 / ADDR→POI 594, 占错误 87%) 以标签噪声+体系边界为主, 与 clean 0.9919 vs 含噪 0.9059 差距自洽; **含噪口径可修复空间 ~1-2pt 上限, 提升正路是评测集标签治理而非模型调参**
- **A 二期特征实验 (回退)**: `d4_strong_poi`/`poi_d4_strong_poi` 强 POI 后缀特征 (80 维) 重训 → val macro-F1 0.9035 < 0.9052 未过门禁, 12 条真错误点查 0 翻转; 回滚 features.py + 删除 f2 artifacts + val_pred.csv 恢复 baseline 重算 (HANDOVER §6/§7)

## v4.0.2 (2026-08-05) — POI 召回攻坚 (D0 诊断 + 口径分层, A 实验回退)

无算法/词典变更（D1-A 重训实验回退, baseline clf_v3.pkl 不换）。

- **漏迁移捕获**: `compute_metrics/print_metrics` 提取至 `tools/metrics.py`（v3/train|evaluate|clean_eval 依赖, 重训时才发现, 踩坑 #23）
- **POI 召回攻坚 D0 诊断**（`v3/poi_recall_audit.py` → output/v4_poi_recall_audit.md）: 纯净召回 57.5% 分解为 真边界 ~35-40pt (机关→ORG 19.4% + 交叉口/楼栋门牌/自然地名→ADDR) + 真错误 ~5-7pt (公园/寺山/广场/大厦/门店 高置信误判 ADDR); 机制=专名含地名抬 geo_cov + eval 标签寺/景区→ADDR 倒挂
- **口径分层 (B 路线, 已落地)**: `v3/pure_eval.py report` 新增分层口径——POI 有效召回 **84.0~85.8%** (真边界剔除), ORG ≈100%
- **模型修复实验 (A 路线, 回退)**: `v3/augment_poi.py` 24K 真错误模式 POI 增强重训, val 持平 0.9050 vs 0.9052, 12 条真错误点查 0 翻转 → 特征驱动非标签量不足, 决策回退 (HANDOVER §6); artifacts 留存 models/clf_v3_poi.pkl + data/v3_augment_poi.csv 备查

## v4.0.1 (2026-08-05) — 迁移后审计 + v3 测试补齐

无算法/词典变更。v4.0.0 迁移后的质量加固版本。

- **v3 测试补齐** 124 → **181 条**（+57）: `test_v3_engine.py`（DPEngine 合成小词典 21 条: Trie 碰撞优先级/词成本/短 d4 惩罚/8 个后处理钩子）、`test_v3_pipeline.py`（后处理四方法+三表懒加载 15 条）、`test_suffix_classify.py`（core 直测 6 条）、`test_v3_brand_model.py`（v3 副本 save/load 回环 6 条）、`test_fast_predict.py`（FastCalibrated vs sklearn 零误差 3 条）、`test_serve.py`（FastAPI TestClient 契约 6 条）
- **迁移后审计修复**: 三文档测试计数失真修正（实际 tests/legacy/ 71 + 根目录 110，旧文案笼统写 112+12）；README 指标表头 v3.9.0→v4.0.x；`serve.py` `@app.on_event` 废弃写法改 lifespan；迁移计划文档加"已执行"眉注

## v4.0.0 (2026-08-05) — v2 代码迁移 /v2/ + FastAPI 生产化

按 `audit/v4.0.0_migration_plan.md` 执行（用户两处拍板调整：pipeline.py 留根改名 `pipeline_v2.py`；`tests/v2/` 因与根 `v2/` 包同名冲突改为 `tests/legacy/`）。无算法/词典变更。

- **V1 切除 v3→v2 依赖**: `classify_suffix`/`_SAFE_SINGLE_SUFFIXES` 提取至 `core/suffix_classify.py`（`v2/loc_importer.py` re-export 兼容）；`v3/pipeline.py` 自包含化（COMPANY/GOV 后缀常量 + 后处理四方法 + d4_map/suffix_table/sql_suffixes 三表懒加载，逐方法复制不改逻辑）；`BrandModel` 复制为 `v3/brand_model.py`；`v3/features.py` 常量改自 `v3.pipeline`
- **V2 物理迁移**: v2 独有代码平铺迁入 `/v2/`（`loc_recognizer/loc_builder/loc_importer/org_recognizer/poi_recognizer/brand_model/eval` + `v2/tools/` 19 个 v2 时代工具）；根 `pipeline.py` → `pipeline_v2.py`（留根，文件名带版本与 `v3/pipeline.py` 区分）；112 条 legacy 测试迁 `tests/legacy/`；`loc/ org/ poi/ brand/` 四空包删除；`v3/engine/gate.py`、`v3/seg_compare_worker.py`、`v3/badcase_eval.py`、`tools/loc_build_v140.py` 的 legacy 基线 import 改 `v2.*`
- **V3 三保险**: 124 tests 全绿；gate 20K diff 计数与迁移前 HEAD 逐项一致（1943/1753/2604，该 FAIL 为既有现象——legacy 识别器锚定 v1.2.x 词典 vs v3 用 v1.5.0，非本次引入）；双 CLI 冒烟通过
- **V4 生产化**: 新增 `serve.py`（FastAPI：POST /classify、/classify_batch、GET /health，单例预加载 V3Classifier）；requirements +fastapi/uvicorn；压测（output/v4_serve_bench.md）：单条 p50 50ms/p99 52ms，批量 1.9ms/条，单 worker 并发受 GIL 限制需多 worker 水平扩展

## v3.9.2 (2026-08-05)

工程收尾版本。新增 `AGENTS.md`（新会话 5 分钟速通：验证三连/文件地图/红线/常用命令）。新增 `audit/v4.0.0_migration_plan.md`（下轮 v2→/v2/ 迁移+FastAPI 生产化的文件级计划）。磁盘治理 ~5GB（iter_v1.4.0、v3_feat 临时分片、被取代的训练合并文件、loc v1.4.0 构建中间态）。无算法变更。

## v3.9.1 (2026-08-05)

文档审计版本。README 全面更新至 v1.5.0 词典/v3 管线; HANDOVER 重构为"框架+管线+血缘+门禁+决策+踩坑"接手手册; 变更记录单拆为 CHANGELOG.md (本文件); 三文档定位与维护原则成文。无代码变更。

## v3.9.0 (2026-08-04) — 置信度审计 + 裁决钩子 + v1.5.0 二轮自举

- **置信度审计** (`v3/calibration_audit.py`): ECE=0.0129 (<0.05 合格线), Brier=0.078。0.9+ 高置信桶 2.7 万样本: 置信 0.967 vs 实际 0.962 — confidence 可作概率路由
- **中部位 TOWN/BRAND 裁决** (`_post_adjudicate_town` 钩子): bare TOWN 非开头+后接 INDUSTRY/POI → BRAND (幸福/鑫源/兴旺/腾达/利民), 镇村合并+政府后缀保护; addr 验证率 90.2%→98.5%; 影响面 5.22% 审查均为改善
- **v1.5.0 二轮自举**: stats 引擎参数化 (STATS_VERSION), v1.4.3 引擎重切; 补丁再固化 (F1 括号 131 条/F5 村委会复合词零新增自愈); seg_compare v1.4.3→v1.5.0: org 7.89% (BRAND -9.4M 碎片合并改善) / poi 4.52% / loc 0%; seg_quality addr 98.6%, low_freq_seq 4.4%
- **自举收敛判断: 词频迭代已收敛, 不建议 v1.6 再自举** (收益进入噪声带)
- test macro-F1 0.9059, 124 tests 全绿

## v3.8.0 (2026-08-04) — 统一版本号 + FastGBDT + 纯净集 + bare 攻坚

- **统一版本号政策** (用户决策): 任一词典变更, loc/org/poi/brand 四词典版本号一起升
- **N4 延迟**: `v3/fast_predict.py` HistGBDT 编译化 (numpy 向量化树遍历+isotonic 复算, 与 sklearn 零误差), 单条 classify 1.5s→50ms (30×), 批量 1.4ms/条
- **N1 纯净集评测** (output/v3_pure_eval_report.md): org_company 5200万/抽样100万 ORG 召回 73.9%, split/poi 4000万 POI 召回 57.5%——误判样例审查均为体系语义边界 (个体户门店↔机构网点), 无系统性错误
- **N2 bare 裸名攻坚**: `v3/bare_prune.py` 位置证据 (2000万语料首尾扫描) 降频 109 个商业后缀族 bare 词 (中心/商店/农场/金店/油坊/鸡场等)
- test macro-F1 0.9075

## v3.7.1 (2026-08-04) — v1.4.2 村委会复合词清除

- F5 d1 村/居委会复合词清除 1,144 条 (`tools/patch_v142.py`): 桥村村民委员会→桥村+村民委员会POI。村委会/居委会是行政机构不是村
- F6 d3 freq<10 清除 56 条
- LOC 词典同名复合词 (VILLAGE 25.4万/COMMUNITY 6.4万) **按语义差异保留**: 地址语境中"XX村委会"是地点, ORG 语境中是机构
- test macro-F1 0.9076

## v3.7.0 (2026-08-04) — v1.4.1 词典清理

- F1 括号归一化 121 条 (有限合伙）族→有限合伙 freq=69万), 新增 leading_bracket 钩子输出整段"（有限合伙）"
- F2 loc>org 误杀复合后缀回补 24 条 (广场/商场/市场/停车场/加油站等, 治"广/商"裸奔碎片) + F2b d1 冲突清理 (广场/市场/庄园 TOWN 词条) + F3 数字垃圾清理 (4S店/2元店白名单保留)
- F4 可读审计面 `dicts/export/{org,poi}_{d1,d3,d4}_*.csv`
- test macro-F1 0.9064

## v3.6.0 (2026-08-04) — v1.4.0 词频全量重统

- **stats bootstrap 换代**: 硬编码 OrgDPRecognizer(v1.1.1) → v3 引擎 v1.3.0 (`tools/org_chunk_stats_v3.py`/`poi_chunk_stats_v3.py`), org 1.65亿/poi 4000万重切统计
- aggregate 重跑 + 补丁固化 (bare互斥/d4互斥/poi_prune重推导) → org/poi_v1.4.0.pkl
- loc 重建 (builder+道路 freq≥10+VILLAGE清理+prune/NUMERIC注入) → loc_v1.4.0.pkl (ROAD 42.4万); brand_v1.4.0 重训
- 回归: seg_compare org 4.45%/poi 4.49%/loc 0.98%; badcase 修复 ORG 6.2%/POI 2.0%/LOC 0.8%; seg_quality 不降
- poi_prune 重推导 203→8 词 (v1.3.0 修复进入统计, 闭环自证)
- test macro-F1 0.9061

## v3.5.0 (2026-08-04) — UNKNOWN 真实样本 + v1.3.0 实体化 + 亿级回归

- UNKNOWN 真实样本扩充: 高德"室内设施" (会议室/桌号/摊位, 非独立实体=UNKNOWN) 23K→去重 11,754 条, 60/20/20 追加进 eval splits (support 10/9→2,360/2,361)
- 词典实体化 v1.3.0 (`tools/bake_v130_dicts.py`, 补丁烘焙, 零差异门禁 5K×3 通过)
- 亿级全量回归 (`v3/seg_compare.py`): org 2.67% / poi 7.21% / loc 10.24%, 均为设计内变化
- run.py 默认切 v3 (v2 用 `run.py v2`); classify_batch 向量化
- **v1.3.0 系统评估** (output/v1.3.0_eval_report.md): badcase 修复率 POI 18.2%/ORG 5.5%/LOC 0.9%, POI 低频序列种类 -14.5%, 无回归项
- test macro-F1 0.9000 (UNKNOWN F1 0.9064)

## v3.4.0 (2026-08-04) — POI 位置证据剪枝

- `v3/poi_prune.py`: poi 名称中 d1 词应在开头 (地址前缀), 千万语料统计首尾位置, 结尾≥85%且≥100次的 TOWN 族词 203 个从 d1 移入 d4 (酒店47.9万/商店29.4万/市场/公园/新村/南区…, SQL 在 poi 语料把后缀错标为 d1)
- 配套: bare-name 注入跳过 d4 词 (治 Trie 碰撞 TOWN 压 POI), 连带根治 ORG 侧同类残留
- POI 末段后缀率 64.7%→68.3%; test macro-F1 0.8016

## v3.3.0 (2026-08-04) — LOC 伪行政词剪枝 + 连词拆分

- 伪行政词剪枝 (`v3/loc_prune.py` → `dicts/loc_prune_v1.3.0.json`): 36 词 (超市/生鲜超市/综合门市等假CITY, 规则=未被areas证实+admin freq<1万+POI freq≥100×)
- "与X路"拆分钩子 (工业路与解放路→ROAD+与+ROAD)
- LOC addr验证率 88.5%→88.9%; test ORG/POI/ADDR F1 0.8684/0.9134/0.9247

## v3.2.0 (2026-08-04) — LOC NUMERIC/POI_SUB 从零建模

- 病灶: LOC 词典 NUMERIC/POI_SUB 两类完全为空 (转移表有规则但词典无词条), 门牌号/楼层/村组全落 UNKNOWN (占 LOC 残差 ~80%)
- 注入数字 0-9+全角 (NUMERIC, freq=5000) + 号/层/楼/栋/单元/室/组等 24 词 (POI_SUB) + 9 条转移规则
- "人民路88号"→ROAD+NUMERIC+POI_SUB, "瓦房村3组"→VILLAGE+NUMERIC+POI_SUB
- LOC diff 7.1% 审查为改善, unknown_char_rate 4.0%→3.4%; test macro-F1 0.8009

## v3.1.0 (2026-08-04) — 清洗二轮 + clean 评测子集 + ORG 商业裸名

- 标签清洗二轮: 类条件阈值 (ORG/POI 0.55, ADDR 0.65) + 高置信矛盾翻转标签 (P≥0.9, 3.5万条翻转+17.9万剔除)
- UNKNOWN 合成增广 5 万条
- clean 评测子集 (`v3/clean_eval.py`): 模型无关查表信号确认标签, val/test 各 ~31%; **clean accuracy 0.9919** — 模型在可信标签上近完美, 原始标签 macro-F1 的"错误"大部分是评测集标签噪声
- R1: bare-name 注入跳过 SQL 主导商业后缀 (38词, 修"商店/酒店→TOWN")
- test macro-F1 0.7913

## v3.0.0 (2026-08-04) — 系统性重构 (GBDT 分类器)

- 分类层学习化: GBDT (HistGradientBoosting) + isotonic 校准 + 类别乘数标定, 替代 ~20 个手调魔法数规则链
- 78 维特征 (段级/查表/统计/规则信号), 训练推理同一代码路径
- 270 万弱标注 (Gaode 2M+Tencent 1M 采样, 防 val/test 泄漏) + confident learning 3-fold 清洗 5.4%
- 统一 DP 引擎 (`v3/engine/`, 与旧识别器 20K 样本零差异)
- eval train/val/test 60/20/20 固定切分 (种子42)
- test macro-F1 0.7699 (v2.2.1: 0.3702); 测试 124 条; v2.2.1 冻结为 baseline

## v2.2.1 (2026-07-11)

段类型体系修复 (SegType.ORG_SUFFIX)。split_polluted_d4 拆分1301条 d4→d3+d4。POI_EXCLUDE_D4 精简(41→29)。_decide 查表调score。LOC VILLAGE 清理(石家庄/枣庄→CITY)。复合机构检测+重识别。过度拆分合并(SQL CSV校验)。badcase 体系。评测18万条, macro-F1=0.3702。词典 v1.2.3。测试112条。

## v2.2.0 (2026-07-11)

数据驱动 classify: d4_category_map (Gaode标注) + suffix_category_gaode (高置信后缀)。移除手工后缀列表。SQL CSV 规则 (d4∉SQL→POI)。Gaode道路名合并入LOC词典 (47万条)。gov seed 29条。

## v2.1.0 (2026-07-10)

`pipeline.classify()` 统一分类: ORG/POI/ADDR/UNKNOWN。csv_index 亲和度评分。gov suffix seed 注入。评测闭环 (18万条 eval_set + 混淆矩阵 + per-class F1)。手工后缀列表驱动。词典 v1.2.1。测试108条。

## v1.2.3 (2026-07-07)

四代审计 F1-F22 全部修复 + Finding 1-19 全部修复。F1/F3/F7 三次迭代回归修正。Trie 碰撞优先级、线程安全、LOC 裸名、gbk fallback、original 字段一致性。测试 90 条。

## v1.2.2 (2026-07-06)

架构重构: H1-H4 + 二代审计 N1-N24 全部修复。新增 `core/config.py`, `core/suffix_matcher.py`, `tools/pipeline_base.py`。删除 `geomodel/`。词典升级至 v1.1.2。测试 77 条。

## v1.2.1 (2026-07-06)

审计修复: 22/50 (Critical 2, High 4, Medium 10, Low 6)。

## v1.1.1

词典收敛版: 四词典统一 v1.1.1, brand 分离度 4.1, poi d4 覆盖 113%。

## v1.1.0

初版收敛词典。
