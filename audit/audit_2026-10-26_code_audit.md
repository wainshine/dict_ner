# 代码审计报告 2026-10-26（v4.2.0 工作树）

> 范围：v3 运行时链路（engine/pipeline/features/infer/fast_predict）、core 共享模块、serve.py/run.py、训练与词典工具链。
> 方式：全量阅读 + 实测复现。基线确认：195 条单测全绿；CLI 双冒烟通过；fast_predict vs sklearn 对拍最大误差 1.1e-14。
> 结论：**无 P0（线上正确性崩溃）问题**；发现 4 个 P1、5 个 P2、11 个 P3。均已给出改进方案，未改任何代码。

## P1 — 高危（数据/产物损坏或不可复现）

### P1-1 train.py 实验重训仍会覆盖基线 manifest_v3.json
- 位置：[v3/train.py](../v3/train.py) L119、L225。`--manifest` 默认恒为 `models/manifest_v3.json`，不随 `--model` 变化。v4.2.0 只给 val_pred 加了防覆盖（`resolve_val_pred_path`），manifest 是同类坑（踩坑 #24/#27 的孪生）：一次实验重训即覆盖基线 manifest（md5 血缘/tuned 指标/时间戳全丢，无 .bak）。
- 复现逻辑：`python v3/train.py --model models/exp.pkl` → 仍写 `models/manifest_v3.json`。
- 改进：manifest 路径默认由 model 路径推导（`manifest_<model_stem>.json`），仅当 `--model` 为基线时写 `manifest_v3.json`；或对基线 manifest 写前 `shutil.copy2` 留 .bak。建议补一条类似 `TestValPredPath` 的回归测试。

### P1-2 v4.2.0 分组切分与 final_train7 构建脚本不在仓库（重建不可复现）
- 证据：全仓 grep `StratifiedGroupKFold` 零命中；`final_train7`、`eval_split_group` 无任何 .py/.md 引用。`v3/make_split.py` 仍是旧随机切分（`train_test_split(stratify=)`，L46-50）。
- 现状数据本身是对的：`data/eval_split_{train,val,test}.csv` 与 `eval_split_group_*` md5 完全一致（115,540/38,513/38,513），三集文本重叠 0 已由 v4.2.0 实测确认。但按 README/HANDOVER §8 重建链走 `make_split.py` 会得到**旧的含泄漏切分**（test 9.49% 文本重叠），"额外执行分组切分"一步无脚本可循。
- 改进：补 `v3/make_group_split.py`（StratifiedGroupKFold(5, group=text, seed=42)，fold0-2/3/4）并将 final_train7+calib_feats 构建（剔新 val/test/calib 文本 + 补新 train 行 + 划 held-out calib）落成脚本，同步进 §8。

### P1-3 sample_pool.py 蓄水池采样实现错误（训练池分布偏差）
- 位置：[v3/sample_pool.py](../v3/sample_pool.py) L95-100。缓冲区满后 `j = random.randint(0, len(buf)-1)`，此时 `len(buf) == target`，`j < target` **恒真** → 之后每个有效样本都必然替换一个随机槽位。早期样本存活概率 (1-1/k)^n 指数衰减（如 k=100、后续 n=10⁴ → ≈e⁻¹⁰⁰≈0），按 type 的采样实质上是"取目录扫描顺序最后若干文件的样本"。
- 影响：`data/v3_train_pool.csv`（270 万）即由此构建，当前模型训练分布受此偏差；因原始语料已删，偏差无法追溯修正，但脚本必须修好供未来重建。
- 改进：标准蓄水池（维护已见计数 i，`j = randint(0, i)`，`j < k` 才替换），或两遍扫描 + 定长采样。`v3/sample_unknown.py` L72-74 的室内设施采样同理非均匀（替换概率固定 1/20，偏向早期文件），建议一并改标准蓄水池。

### P1-4 CsvIndex 懒加载无锁：serve 冷启动并发重复加载（实测复现）
- 位置：[core/csv_index.py](../core/csv_index.py) L65-87。三个属性 `suffix/trade/addr` 都是 `if self._x is None: self._x = _load(...)`，无锁、无启动预热。uvicorn 同步端点跑线程池，worker 启动后第一波请求并发首次访问。
- 实测：4 线程同时首次触发 → `addr_segments_sql.csv`（200 万行）被**完整加载 4 次**（每次 ~4.2s，1,421,170 条 AffinityEntry 对象）；每 worker 每进程都会发生一次。瞬时 CPU/内存放大 N 倍（4×~300MB 级），且首波请求全部阻塞 ~4s。
- 改进：与 `V3Pipeline` 三表一致的双检锁（`with self._lock`）；或在 `serve.py` lifespan 里显式预热 `idx.suffix/trade/addr` 后再收流量；`CsvIndex.instance()` 的 check-then-act 也建议加锁防双实例。

## P2 — 中危（健壮性/性能/安全面）

### P2-1 serve.py 无输入上限 + `_clf` 可能为 None
- [serve.py](../serve.py)：`ClassifyRequest.text` 无 max_length、`BatchRequest.texts` 无条数/单条长度上限。一个超大 batch（如 10⁵ 条）一次请求可放大为全量特征提取+三体系段结果，长时间占用线程池工作线程（CPU/内存 DoS 面）。改进：pydantic 约束（如 `Field(max_length=...)`、`max_items`）+ 超限返回 422/413；必要时加 batch 内部超时。
- 端点体直接 `_clf.classify(...)`：若 lifespan 未执行（异常启动路径/测试直调）→ `AttributeError` 500。改进：模块级 `_get_clf()` 惰性初始化（带锁），或端点内 None 检查返回 503。

### P2-2 fast_predict 依赖 sklearn 私有 API，版本无上限、启动不自检
- [v3/fast_predict.py](../v3/fast_predict.py) L18-24 读 `hist_gbdt._predictors`、`_baseline_prediction`；[requirements.txt](../requirements.txt) 仅 `scikit-learn>=1.5`。sklearn 2.x 改内部结构时，[v3/infer.py](../v3/infer.py) L58-62 的 `try/except` 会**静默回退慢路径**（单条延迟 25×）而无人知晓。本机 1.9.0 对拍 1e-14 通过（`validate()` 存在但推理启动时未调用）。
- 改进：requirements 上限 `<2.0` 并写明支持矩阵；`V3Classifier.__init__` 启动时用小随机矩阵跑一次 `validate()`，误差超阈值即告警/拒绝；至少 log 回退原因。

### P2-3 lookup_trade 全表扫描占推理热路径 ~40%
- [core/csv_index.py](../core/csv_index.py) L99-106：每次调用遍历全部 40,453 条 trade 词做 `w in text`。实测 1.1ms/次；含 INDUSTRY 段文本的单条 classify 实测 **2.81ms**（README 口径 2.1ms），其中 trade 查表约 40%。
- 改进：构建子串索引（按长度桶 + 首字倒排，或 Aho-Corasick）；表一次性 load 后固化，查询从 O(N) 降到 O(候选数)。

### P2-4 引擎构建函数默认版本陈旧且与门禁叙述不符
- [v3/engine/configs.py](../v3/engine/configs.py)：`build_loc_engine()` 默认 `loc_v1.3.0`、`build_org_engine()` 默认 `v1.3.0`、`build_poi_engine()` 默认 `poi_v1.3.0.pkl`，与生产 v1.5.0 不一致；[gate.py](../v3/engine/gate.py) L42-47 直接吃默认 → 门禁实际对比的是 **v1.3.0 vs legacy v1.2.x**，与 HANDOVER §4.2「v1.5.0 词典 vs legacy」的叙述不符。
- 改进：默认值统一取 `core.config.VERSION`（单一来源），或移除默认强制显式传参；gate 的词典版本说明同步修正。

### P2-5 POI_SUFFIX_MAP 缺失时完全静默降级
- [core/types.py](../core/types.py) L93-101 模块导入时加载 `dicts/poi_suffix_category.csv`——该文件在 [.gitignore](../.gitignore) 中（git 不追踪）。clone 后缺失 → `POI_SUFFIX_MAP={}` **无任何 warning**，`classify_suffix` 全部退化返回"建筑"，loc 引擎 admin-pattern 的 POI 后缀匹配退化。与 v4.1.2 给 pipeline 三表补 warning 的约定不一致。
- 改进：加载失败/缺失时 `logging.warning`；HANDOVER §3.5 缺失行为清单补该文件。

## P3 — 低危（潜伏 bug / 卫生 / 一致性）

1. **转移表重复键死赋值**：[configs.py](../v3/engine/configs.py) L176/L178 `(UNKNOWN,POI)` 先 2.0 后 0.2，2.0 为死代码（v2/org_recognizer.py L320/L339 同源，属历史移植）。建议 v3 删死行并注释 0.2 为最终值。
2. **`_merge_over_split` 合并后不更新 `s1.end`**：[v3/pipeline.py](../v3/pipeline.py) L153-157。实测 30K 抽样：868 条发生合并、885 个段 `end != start + len(text)` 不变量破坏（如 `'蔬菜产业' start=6 end=8`，len=4）。当前下游（to_dict 不含 start/end、_detect_compound 只读 ORG_SUFFIX 段）未踩雷，属潜伏；建议 `s1.end = s2.end`。
3. **CLI 冷启动 ~12s**：实测 `run.py classify` 墙钟 12.1s = loc 词典 3.3s + org/poi 引擎 ~1.3s（含 `_build_bare_name_table` 每引擎重读 4 个区划 CSV、无缓存）+ 模型 1.1s + 首次请求触发 addr 表懒加载 4.2s。改进：bare 表进程内缓存；serve lifespan 预热三表；CLI 可选。
4. **precompute 内存与健壮性**：[v3/precompute.py](../v3/precompute.py) `split()` 全量 `list(csv.reader(f))` 读入内存（270 万行×~90 列，数 GB 级）；`merge()` 不校验各 chunk header/行数；`main()` 缺参数抛裸 IndexError。
5. **labels.py 三处小坑**：[v3/labels.py](../v3/labels.py) `--drop-org 0` 因 `or` 真值短路无法传 0（L72-75）；pool 3-fold CV 未按文本分组（同文本跨 fold，清洗置信度偏乐观）；脏标签 `map(L2I)` 产出 NaN 而非报错。
6. **metrics 口径**：[tools/metrics.py](../tools/metrics.py) 遇 LABELS 外标签直接 KeyError（无容错）；macro-F1 由**四舍五入后**的 per-class F1 求均值，文档宜注明口径。
7. **launch_parallel 超时未处理**：[tools/pipeline_base.py](../tools/pipeline_base.py) L105 `communicate(timeout=3600)` 抛 TimeoutExpired 未捕获 → launcher 崩溃、16 个子进程存活泄漏；失败 worker 可能留半截 stats pkl（aggregate 只按存在性校验 16/16，pickle.load 时才炸）。
8. **补丁脚本卫生**：patch_v141.py `F3_KEEP` 重复定义（L69/L85）、`f2b_d1_conflict_clean` 的 d4 参数未用；patch_v142.py docstring 自认 F5 未按描述校验村名；stats_launch_v3.py iter 目录取 `DICT_VERSION`（默认 v1.5.0）而非 `STATS_VERSION`，双 env 口径易混。
9. **seg_quality 门禁慢循环**：[v3/seg_quality.py](../v3/seg_quality.py) L129 `sum(1 for sfx in sql_suffixes ...)` 对每个末段后缀样本全表扫 24K 后缀且不短路——20 万样本门禁很慢；`any()` 短路或索引化。
10. **run.py 卫生**：顶层 `from pipeline_v2 import DictNerPipeline`（实测导入仅 0.02s，影响小）；`--batch` 缺文件参数裸 IndexError；`cmd_classify_batch` 整文件读内存。
11. **发版未提交**：v4.2.0 工作树脏（7 文件 modified + 2 个 baseline 文件 untracked，`origin/main` 落后 1 提交），违反红线 #4/#6「发版 = 代码+四文档+git 提交」。建议尽快提交或明确状态。

## 已确认良好的部分（审计核实）

- **#31 并发修复扎实**：`extract_with_results` 全局部变量 + thread-local 兼容接口 + 8 线程回归测试（tests/test_v3.py L89-111）——实测 300 条单条 2.81ms/条、批量 2.13ms/条，无串扰。
- **atomic_pickle_dump**（tmp + os.replace + .bak）覆盖词典链写路径，测试齐全（TestAtomicPickle）。
- **模型特征 schema 校验**（V3Classifier L47-56 拒绝加载不一致模型）；词典 pkl fail-fast（FileNotFoundError）；fast_predict 对拍误差 1.1e-14。
- **数据现状正确**：group split 三集文本重叠 0（md5 实证 eval_split_* == eval_split_group_*）；manifest 血缘字段指向现役路径；195 测试全绿。
