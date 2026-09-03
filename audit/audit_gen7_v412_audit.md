# dict_ner v4.1.2 自审计修复计划（主会话7代）

> 审计日期 2026-09-03。范围：代码-文档一致性 / 功能与测试 / 文档体系完整性与分工。
> 本计划经用户批准范围：**A（文档修正）+ B（结构补强）+ C（产物重跑）全做，按 v4.1.2 发版准备，git 提交由用户自行完成。**

## 0. 审计总结论

- **功能/测试健康**：188 测试全绿（51.9s）；v3/v2 classify、recognize 冒烟通过且输出与 README 示例逐字一致；README/AGENTS 全部 15 条命令与脚本 argparse 静态核对吻合；文件地图所列路径全部存在；词典条目数与文档一致。
- **一致性实锤问题 8 条**（下详），集中在 HANDOVER 陈旧值与悬空引用、manifest 路径字段、个别产物陈旧。
- **文档体系健康**：四文档零死链、分工成文；最大缺口 = git 仓库边界（clone 重建场景）未文档化 + 运行时 CSV 缺失静默降级。
- **project.md / HANDOFF.md 无需补充**：角色已被 AGENTS.md（速通）+ HANDOVER.md（手册）完整覆盖。

## 1. C 档：已完成（计划模式下已执行的测量）

| 动作 | 结果 |
|---|---|
| `v3/evaluate.py --feats test_feats.csv --report output/v3_error_report.md` | ✅ 已刷新（该文件原系 v3.5.0 前陈旧产物）。**完全复现 README 数字**：acc 0.9098 / macro-F1 0.9092 / per-class 0.8650/0.9115/0.9270/0.9331 —— README 数字从此有落盘出处 |
| `v3/seg_quality.py --engine org --n 200000 --v3 --out output/v3_seg_v412_org.json` | ✅ 现役词典复测：末段 97.78% / 后缀 97.89% / 行业 99.23% / **addr 98.62%** / **低频 4.40%** —— 证明 README/HANDOVER 的 98.6%、4.4% **本来就是对的**（审计 agent 对照的 v143adj 产物是 v1.4.3 旧词典），仅行业 99.3→99.2 需改 |
| `v3/seg_quality.py --engine loc ... --out output/v3_seg_v412_loc.json` | ✅ unknown_char_rate = **3.61%** → README 的 3.4% 陈旧，需改 3.6% |
| manifest 血缘验证 | ✅ md5 实证：`final_train6.csv`=manifest train_md5、`val_feats.csv`=val_md5、行数=n_train+1。血缘未断，仅路径字段陈旧（6b/v2 为改名前临时名） |
| CHANGELOG v3.9.0 "98.5%/98.6% 两写" | 结论：**不改历史**。98.5 出自 v1.4.3 词典产物 v143adj，98.6 系 v1.5.0 现役口径，复测证实 98.6 正确；在 v4.1.2 节中注明即可 |

注意：evaluate 的 --report 与 seg_quality 的 --out 是在 plan 模式下已通过 bash 执行的写入（output/ 全目录不受 git 追踪，未污染仓库）。剩余 C 档待办：删除陈旧孤儿产物 `output/v3_test_report.md`（旧口径 0.9059，无任何代码/文档引用，不受 git 追踪）。

## 2. 待执行编辑清单

### 2.1 `models/manifest_v3.json`（A 档）
- L4 `"train_path": "output/v3_feat/final_train6b.csv"` → `"output/v3_feat/final_train6.csv"`
- L6 `"val_path": "output/v3_feat/val_feats_v2.csv"` → `"output/v3_feat/val_feats.csv"`
（md5/n_train 已验证不变）

### 2.2 `output/v4_serve_bench.md`（A 档）
- L5 `## v4.0.2 优化后 (fast_predict 树间批量化)` → `## v4.0.3 优化后 ...`（树间批量化属 v4.0.3，CHANGELOG 可证）

### 2.3 `audit/HANDOVER.md`（A+B 档）
1. L1 头部 `v4.1.1` → `v4.1.2`；L8 §0 系统版本 → v4.1.2
2. L26 维护原则 3 修正（原表述不可达成——两个 VERSION 语义不同）：
   `三文档头部版本号与 run.py VERSION、core/config.py VERSION 保持一致` → `四文档头部系统版本号与 run.py VERSION 保持一致；core/config.py VERSION 是词典版本，与词典版本号（当前 v1.5.0）保持一致`
3. L90 §1.4：`ECE=0.0129` → `ECE=0.0149`
4. L165 §3.4：`gov_suffix_seed.csv` 29 条 → 30 条（实际 31 行含表头）
5. L178 §4.1：POI `84.0~85.8%` → `85.5~87.3%`（v4.0.5 刷新值，产物 v3_pure_eval_report.md L64）
6. L179 §4.1：`ECE 0.0129` → `ECE 0.0149`
7. L222 §6（D1-A 回退行）：`模型 artifacts 留存 models/clf_v3_poi.pkl 备查, baseline 不换 (v4.0.2)` → `baseline 不换 (v4.0.2)；artifacts clf_v3_poi.pkl 已于 v4.1.0 磁盘治理删除（见 §4.3）`
8. L228 §6（v1.6.0 回退行）：`artifacts: dicts/*v1.6.0.pkl + models/clf_v3_v160.pkl + dicts/iter_v1.6.0/` → `artifacts: dicts/*v1.6.0.pkl 留存作证伪留档；clf_v3_v160.pkl 与 iter_v1.6.0/ 已于 v4.1.0 清理（见 §4.3）`
9. §0 L11 段健康度行：**不改**（复测证实 97.9/98.6/4.4 均正确）
10. 文档定位表（L15-21）与维护原则（L25）：增加 AGENTS.md 行 + "发版三件套"→"发版四件套（含 AGENTS.md）"
11. §5 治理规则 6（L205）：`三件套` → `四件套（README/HANDOVER/CHANGELOG/AGENTS.md）`
12. **新增 §3.5「仓库边界（git 追踪范围）与文件获取」**（B 档核心），内容要点：
    - git 追踪：代码 + 文档 + `dicts/*.pkl` + `models/`；**不追踪**：`/data` 全部（split 语料/SQL 三表/eval splits/种子）、`dicts/suffix_category_gaode.csv`、`/dicts/export`、`/dicts/iter_v*`、`/output`（.gitignore 实证）
    - 缺失行为 = **静默降级**：`v3/pipeline.py:85-95` suffix_table 置 `{}`、`core/csv_index.py:26-27` 亲和度返回空、`pipeline.py:105` sql_suffixes 置空集——不抛错，分类可跑但查表特征全零，指标低于文档值
    - 获取途径：本机完整目录 / 异地备份；衍生产物再生路径（stats→aggregate→export；eval_cut.py 从 split/ 重切）
13. §7 踩坑新增 **#30**：文档多址记载的数字在刷新时漏改（ECE 0.0129/POI 84.0~85.8% 两处 v4.0.4/4.0.5 漏改 HANDOVER，v4.1.2 审计发现）——教训：同一事实尽量单一出处，多址记载需列刷新清单

### 2.4 `README.md`（A+B 档）
1. L1 标题 / L5 状态行：v4.1.1 → v4.1.2
2. 文档体系表（L10-14）：增加 AGENTS.md 行（新会话速通，发版同步）；L16 原则③「三文档」→「四文档」
3. 段健康度表：L125 行业验证率 `99.3%` → `99.2%`；L127 LOC unknown `3.4%` → `3.6%`（其余三项复测确认不动）；表下注或 HANDOVER 注明产物 = v3_seg_v412_{org,loc}.json
4. 评估体系表 gate 行（L217）：`引擎一致性门禁 (新旧零差异)` → 加现状注记 `（当前 v1.5.0 词典 vs legacy v1.2.x 有代差，现状预期 FAIL；验收看 diff 计数与变更前一致，见 HANDOVER §4.2）`
5. 重建流程 step 7（L200）gate 行加同样注记（简版）
6. 目录结构 models 行（L156）：补 `clf_v3_compact.pkl` 说明（150树×4类小模型，v3.4 时代备选，非现役基线）
7. 目录结构 audit 行（L161）：补 `（temp/ 为 v1 时代中文审计存档）`
8. 「依赖与测试」节末补一行：`许可证：Apache License 2.0（见 LICENSE）`
9. 版本记录表首行插入 v4.1.2 行

### 2.5 `AGENTS.md`（B 档）
1. L11 当前状态：v4.1.1 → v4.1.2
2. 红线 4：`发版 = 代码 + README/HANDOVER/CHANGELOG 三文档 + git 提交` → `四文档（含本文件）`
3. 红线新增第 7 条：`train.py 无条件覆盖 output/v3_feat/val_pred.csv —— 实验重训（--model 指向新文件）后必须用 baseline 模型重算恢复（踩坑 #24/#27，已踩中两次）`
4. 文件地图 output/ 行：白名单表述补 `synth_feats / unknown_*_feats / pool_clean*_stats.json`（现役实际内容）

### 2.6 `CHANGELOG.md`（A 档 + 新节）
1. 顶部新增 `## v4.1.2 (2026-09-03)` 节，要点：
   - 7 代会话自审计：文档一致性修正（HANDOVER ECE 0.0149 / POI 有效召回 85.5~87.3% / 悬空 artifacts 引用 / gov seed 30 条 / manifest 路径字段）
   - 产物刷新：v3_error_report.md 重跑**复现** test 0.9092/0.9098（README 指标从此有落盘出处）；seg_quality 现役词典复测（v3_seg_v412_*：org 97.8/97.9/99.2/98.6/4.4 确认文档值，loc unknown 3.6% 修正 README 3.4%）；删除陈旧孤儿 v3_test_report.md
   - 结构补强：HANDOVER 新增 §3.5 仓库边界；AGENTS.md 纳入发版四件套 + 红线补 val_pred.csv 坑；README gate 注记 + LICENSE + compact 说明
   - v3.9.0 节内 addr 98.5%/98.6% 两写说明（不同词典版本产物，现役口径 98.6%，历史不改）
   - **无代码逻辑变更**（仅 run.py VERSION）
2. v3.9.0 节（L92-94）：**不改**（见 §1 结论）

### 2.7 `run.py`（版本）
- L2 docstring 与 L7 `VERSION = "v4.1.1"` → `v4.1.2`（tests 无系统版本断言，test_config.py 断言的是词典版 v1.5.0，不受影响）

### 2.8 产物清理（C 档收尾）
- 删除 `output/v3_test_report.md`（陈旧、无引用、不受 git 追踪）

## 3. 不做的事（审计结论）

- 不新建 project.md / HANDOFF.md（AGENTS.md + HANDOVER.md 已覆盖该角色）
- 不新建 CONTRIBUTING（单人维护期，红线 + HANDOVER §5 已承担）
- 不新建正式 HTTP API 文档（3 端点 + FastAPI 自带 /docs，可选项）
- 不改 CHANGELOG 历史条目（v3.9.0 两写系不同词典版本产物，在新节注明）
- 不动 `models/manifest_v3_compact.json`（v3.4 时代归档模型，非现役）
- 不动 v2 冻结文件、不删 v1.1.x/v1.2.x 词典

## 4. 执行后验证

1. `python3 -m unittest discover -s tests/` → 188 全绿
2. `python3 run.py classify "深圳市南山区华为技术有限公司"` → ORG；`run.py info` 显示 v4.1.2
3. 三文档 + AGENTS 头部版本号一致 = v4.1.2；`grep -rn "0.0129\|84.0~85.8\|clf_v3_poi.pkl 备查" README.md AGENTS.md audit/HANDOVER.md` 应零命中（CHANGELOG 历史除外）
4. `git status` 交还用户审查，由用户自行提交
