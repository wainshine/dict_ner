# 审计复核报告 2026-10-26（提交 bb3857e「更新」后）

> 对上轮 `audit/audit_2026-10-26_code_audit.md` 提出问题的修复做逐项复核。
> 方法：读 diff + 独立实测对拍（md5/行级/并发/性能）。工作树干净，196 测试全绿。
> 结论：**6 项重点复核全部通过**；发现 2 个复现链残留缺口（均非阻塞，附改进方案）；两项已知限制**可接受**（条件见文末）。

## 逐项复核

### 1. make_group_split 复现 —— 通过（1 个行序小缺口）
- 用 `eval_split_*.csv.bak_v42`（原始随机切分）作输入复跑：
  - val/test：与现役 `eval_split_group_*`/`eval_split_*` **md5 字节级一致** ✓
  - train：行集合完全一致（115,539 行零差），**行序不同**——原产线按 fold-major（fold0→1→2）输出，脚本按输入序输出；已用 fold-major 重建验证与现役逐行一致（fold-order 重建 = 现役 ✓）
- 幂等性：对现役已分组文件再跑一次，三文件 md5 与现役**完全一致**（行集合分配对输入行序不敏感，无"二次分组漂移"footgun）✓
- 改进：train 输出改为 fold-major 顺序（fold0/1/2 各按输入序）即可从 .bak_v42 达成完全字节级复现（约 1 行改动）。

### 2. build_train7 复现 —— 完全通过（超出文档声称）
- 复跑输出与现役产物**字节级 100% 一致**：`final_train7.csv` 2,629,943 行同位一致 100%（含特征值）；`calib_feats.csv` 23,609 行一致；train_add 33,276 行一致；内建泄漏校验 val/test/calib 重叠 0 ✓
- 数字与 CHANGELOG 完全吻合（2,629,943 / 23,609 / 33,276）。
- 残留缺口：`final_train6.csv` 的**生成脚本缺失**——README/HANDOVER 重建链中 `v3_train_pool.csv → labels → pool_feats_clean2 → final_train6` 的合并步骤无脚本（build_train7 依赖 final_train6 作输入，HANDOVER §4.3 称其"可再生"但路径断链）。建议补 build_train6 脚本或在重建链标注"final_train6 需从备份恢复"。

### 3. manifest 路径推导 —— 通过
- `resolve_manifest_path`：显式 `--manifest` 优先；基线（abspath 等于 clf_v3.pkl）→ `manifest_v3.json`；实验模型 → 同目录 `manifest_<stem>.json`。逻辑正确，无副作用。
- 测试覆盖（TestValPredPath 扩展 3 断言）；`--train`/`--calib-set` 默认值同步改为现役 final_train7/calib_feats ✓。

### 4. CsvIndex 锁/预热 —— 通过
- 实例与三表属性全部双检锁。实测 4 线程并发首访 `addr`（200 万行）：**只加载 1 次**（修复前 4 次），耗时 2.8s（csv.reader 列索引重写比旧 DictReader 的 4.2s 更快）✓
- `serve.py` lifespan 预热实测生效：启动后 suffix 24,039 / trade 40,453 / addr 1,421,170 已加载，首请求 33ms ✓
- 回归测试 `TestCsvIndexLock` 存在且通过 ✓。

### 5. lookup_trade 语义 —— 通过
- 独立对拍 3000 条随机组合文本（新旧实现）：**0 mismatch**。平局语义保持等价：最长匹配、同长取 CSV 文件序最小（旧实现"迭代序首个"等价）✓
- 性能实测 1.1ms/次 → 0.005ms/次（~200×），热路径瓶颈消除 ✓。

### 6. precompute 流式切分 —— 通过
- round-trip 完整性：1000 行 → 16 chunks（每 62/63 行）→ 总数无损 ✓；空输入 SystemExit 拦截 ✓；merge 增加 header 一致性校验 ✓；main 缺参数不再裸 IndexError ✓
- 附注：round-robin 替代旧连续分块，chunk 分布变化对下游无影响（merge 重建、行序不影响训练语义）。

## 其他抽查（diff 全面核对）

- gate 实测 20K：**loc 1976 / org 4249 / poi 2783**，与 CHANGELOG/HANDOVER §4.2 新基线完全一致（默认版本已切 v1.5.0 且口径修正）✓
- serve 上限实测：text 1025 字 → 422；batch 2049 条 → 422；未就绪 503 保护 ✓
- run.py batch 分块（1000/批）+ 缺失文件 exit=2 ✓
- 死赋值清理、`s1.end=s2.end`、labels group CV/`--drop-* 0`/NaN 校验、metrics 未知标签报错、sample_pool/sample_unknown/build_eval_set 标准蓄水池（j∈[0,seen]，P=target/(seen+1) 正确）、patch_v141 重复常量、patch_v142 `--validate-villages`（默认关保持 v1.5.0 重建行为）、launch_parallel 超时 kill、stats_launch 双 env 打印、requirements `scikit-learn<2.0` + FastCalibrated 回退日志、POI_SUFFIX_MAP 缺失 warning —— 均正确 ✓
- 196 测试全绿；工作树干净（发版已提交，红线 #4/#6 达成）✓

## 两项已知限制的可接受性评估

| 限制 | 现状 | 评估 |
|------|------|------|
| CLI 冷启动（实测 9.2s，文档 ~11.5s） | 已做 lru_cache（bare/sql_suffix）、csv.reader 解析、serve lifespan 预热；CLI 侧剩余为 loc 词典反序列化 3.3s + addr 表 2.8s + 模型 1.1s，数据规模固有 | **可接受**。serve 场景已彻底消除（预热后首请求 33ms）；CLI 单次交互可容忍；文档 #39 已记载并给出后续方向（trie/pickle 快照或常驻进程），无需本版处理 |
| 存量 270 万训练池采样偏差 | 原始语料已删，偏差不可回溯；脚本已修复供未来重建；文档 #37 记载充分 | **可接受（带条件）**。当前模型是该池产物且通过全部门禁，不构成回滚理由；条件：任何未来完整重建必须用修复后的蓄水池重采样（会改变训练分布 → 重训 + 全门禁），建议在 README 重建链标注此点 |

## 残留建议（非阻塞，供下轮）

1. `make_group_split.py` train 输出改 fold-major 顺序 → 从 .bak_v42 出发的完全字节级复现（当前仅行序差）。
2. 补 `final_train6` 构建脚本（pool_clean2 + synth + group-train 行特征合并），或在重建链明确标注其需备份恢复——当前 build_train7 依赖它作输入，重建链在此断点。
3. 文档补一条：clone/异地重建时（无 `.bak_v42`）split 行集合不可复现，只能生成同方法等价新切分，指标会有细微波动（零泄漏保证不变）。
4. （可选）`V3Classifier` 启动时跑一次 `fast_predict.validate()` 自检（函数已存在），把 sklearn 私有 API 变化从"静默慢路径"升级为"启动告警"。
