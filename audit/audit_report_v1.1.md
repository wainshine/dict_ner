# dict_ner 二代审计报告 v1.1

> **审计代次**: 第二代 (独立深度审计,非 v1.0 遗留续审)
> **审计日期**: 2026-07-06
> **被审项目**: dict_ner v1.2.2 (词典 v1.1.2)
> **审计范围**: 逻辑正确性 + 数据完整性 + 测试质量 + 与 v1.0 剩余项合并
> **审计方法**: 三路并行 agent 深度代码追踪 + 运行时探测验证
> **新发现**: 24 条 (Critical 5 / High 4 / Medium 8 / Low 7)
> **合并 v1.0 遗留**: 15 条 → 合计 39 条
> **本报告仅描述故障,不提供修复方案**

---

## 0. 执行摘要

v1.0 审计聚焦代码风格(命名、重复、魔法数字、logging),**未触及逻辑正确性**。二代审计补上这一维度,发现 5 条 Critical 级功能性 bug——其中 N5 (`pipeline.py:45` poi_dict 参数被丢弃) **线上就在错**,N3/N4 使文档宣称的"从零重建"**实际跑不通或产出空词典**。

同时核查测试质量:77 条用例全过是**虚假绿灯**。最严重的 N5 没有任何测试能捕获,因为测试只断言"返回了 dict""段数 > 0"这类同义反复。loc/org 两个 DP 引擎共 60+ 条转移代价,**0 条单测**。

v1.0 剩余 15 条风格类问题合并入本报告总清单,经冲突分析:3 处与二代新发现存在关联(详见 §8),其余独立。

---

## 1. Critical (5 条) — 已上线 bug 或重建即崩

### N1 · `_cleanup_chars` 死代码:停用字过滤永不执行
- **位置**: `loc/recognizer.py:396` (cleanup 分支) + `loc/recognizer.py:311` (relabel 起因)
- **故障**: `_backtrack` 在单字回退时把 segment 标为 `SegType.UNKNOWN` (line 311)。但 `_cleanup_chars` (line 396) 检查的是 `if seg.seg_type == SegType.CHAR:`——`CHAR` 类型在回退后的 segment 列表中**根本不存在**(CHAR 仅在 DP 内部 `dp[i+1]` 元组里出现,从不进入 segments)。因此停用字过滤分支 `"".join(ch for ch in cleaned if ch not in STOP_CHARS)` 永远不执行。
- **触发条件**: 任何含停用字(`，。；、！？：,.!?;: \t`)的未识别部分。例:`recognize("北京，")` 产出含 `'，'` 的 UNKNOWN 段。
- **可观测影响**: 全角标点污染 segment.text。`recognize("北京市，南山区")` 的 DISTRICT 段 text 为 `'，南山区'` 而非 `'南山区'`,下游 `_detect_poi_type`、`classify_suffix` 及消费者均看到脏文本。
- **与 v1 关系**: v1 M17 修了 `_cleanup_chars` 内的 `end = start + len(cleaned)` 算术 bug,但**没发现整条分支不可达**。M17 修复有效(若 N1 修复让分支可达,M17 算术仍需保留),但单看 M17 是"修了死代码里的算术"。

### N2 · `TRAILING_SINGLE` 合并死代码:尾字永不被吸收
- **位置**: `org/recognizer.py:441-443` (relabel) + `org/recognizer.py:452` (dead check)
- **故障**: 441-443 行先把**所有** `SegType.UNKNOWN` segment 重标为 `SegType.BRAND`,随后 452 行才检查 `if last.seg_type == SegType.UNKNOWN ...`。此时已无 UNKNOWN segment,条件恒为 False,合并永不触发。27 字 `TRAILING_SINGLE` 集合 `{店,厂,站,路,村,屯,镇,乡,街,馆,铺,坊,...}` 的吸收逻辑沦为废代码。
- **触发条件**: 任何 ORG/POI 文本以单个未识别的后缀样字结尾、且前段为 INDUSTRY/POI/ROAD。例:`recognize("XX公司店")` → `[BRAND 'XX', POI '公司', BRAND '店']` 而非 `[BRAND 'XX', POI '公司店']`。
- **可观测影响**: `XX咖啡店`、`YY餐饮馆`、`ZZ便利店` 等的末字被拆成独立 BRAND 段,识别碎片化。POI 后缀吸收失效。

### N3 · POI 重建产出空词典:源文件不存在且静默跳过
- **位置**: `tools/poi_launch.py:10-12` + `tools/poi_dedup.py:44-45`
- **故障**: 硬编码源文件 `兴趣点A(6500w)input.txt` / `兴趣点T(7200w)input.txt` 在 `data/` 下**不存在**(实际只有 `地名A/T input.txt`,README:79 标为"测试集")。`poi_dedup.py` 遇缺失文件 `print("SKIP")` 后继续运行,写出空的 `poi_deduped.txt`。后续 `poi_launch.py` 的 `chunks_exist` 检查在第二次运行时通过(空 chunk 已存在)→ 跳过 dedup+split → 16 个空 chunk 训练出空词典 → **覆盖 `poi_v1.1.2.pkl`**(d4 从 15,384 条变 0)。
- **触发条件**: 删除 `data/split/poi/` 后执行 `python tools/poi_launch.py all`(或 `filter`→`split`→`stats`→`agg`)。
- **可观测影响**: POI 识别完全失效,且无任何错误提示。自投毒机制使后续运行也基于空 chunk。
- **与 v1 关系**: v1 H6 修了 `poi_dedup.py` 模块导入时执行 IO 的问题(移入函数),但**没修源文件缺失时静默 SKIP 并继续**的问题。两问题同位不同层,不冲突。

### N4 · `org_chunk_stats.py` 参数顺序写反:迭代精炼失效
- **位置**: `tools/org_chunk_stats.py:65`
- **故障**: 调用 `OrgDPRecognizer(os.path.join(BASE_DIR, "dicts"), os.path.join(BASE_DIR, "data"))`。`OrgDPRecognizer.__init__(self, data_dir, version=...)` 的签名意味着 `data_dir="…/dicts"`、`version="…/data"`(把路径当版本字符串)。cache_path 变为 `…/dicts/org_/Users/…/data.pkl`(荒诞路径),pickle 加载失败后回退到硬编码 `"v1.1.1"`。
- **触发条件**: 每次执行 org 迭代训练。
- **可观测影响**: 当 `core.config.VERSION` 升至 v1.1.3 时,`org_chunk_stats` 仍加载 `org_v1.1.1.pkl` 进行识别统计——迭代精炼基于旧版识别结果,**无法收敛**。`_inject_d111_missing` 也因版本 substring 不匹配而总是触发。
- **与 v1 关系**: v1 H8 修了 `poi_launch.py:87` 传 `"poi_v1.7"` 的版本不一致,但**没查 `org_chunk_stats.py` 内部的参数顺序错误**。两问题不同文件不同性质,不冲突。

### N5 · `pipeline.py` 丢弃 `poi_dict` 参数:线上加载错误词典版本 ★已上线
- **位置**: `pipeline.py:42-46` (poi property) + `pipeline.py:21` (死属性) + `poi/recognizer.py:8`
- **故障**: `DictNerPipeline.__init__(poi_dict="poi_v1.1.2")` 存了 `self.poi_version`,但 `poi` property 调 `PoiRecognizer(DATA_DIR)` **不传该参数**。`PoiRecognizer.__init__` 默认 `dict_name="poi_v1.1.1.pkl"`。`self.poi_version` 是死属性,从不被读取。
- **触发条件**: 默认 `DictNerPipeline()` 实例化即触发,无需特殊参数。
- **可观测影响**: **线上每次 POI 识别都加载 v1.1.1 而非 v1.1.2**。实测 pipeline 加载 d1=54,710 条(v1.1.1),而 v1.1.2 只有 43,090 条。所有 pipeline 消费者(包括 README 示例)用的都是旧 POI 词典。无任何测试断言 `pipe.poi._rec._dict_name`,所以 77 测试全过也没发现。
- **与 v1 关系**: 全新发现,v1 无对应项。

---

## 2. High (4 条)

### N6 · pattern 匹配 span 含夹带垃圾文本
- **位置**: `loc/recognizer.py:228-234` (`_generate_pattern_matches`)
- **故障**: `word = text[last_boundary:end]` 用**上一个后缀的 end** (`last_boundary`) 作为当前 admin 名匹配的起点,而非当前后缀的 `spos`。两个后缀之间的任何文本(标点、数字、垃圾)都被并入后一个 pattern 匹配的 text 与 span。
- **触发条件**: 输入中两个行政后缀之间存在非后缀文本。实测:`recognize("北京市，南山区")` → DISTRICT 段 text=`'，南山区'`;`recognize("北京市。南山区")` → `'。南山区'`;`；`、`、` 同样。
- **可观测影响**: 行政 segment 的 text 含前导标点,污染下游 POI 分类与消费者。

### N7 · 村名标准化模式相互覆盖产生"社区社区"
- **位置**: `loc/importer.py:11-18, 28-36` (`normalize_village_name`)
- **故障**: 函数对**原串**逐个套用 6 个 pattern,各 pattern 独立替换。`"社区居民委员会"→"社区"` 命中 `"X社区居民委员会"` 产出 `"X社区"`,同时更具体的 `"社区居民委员会"→"社区"` 也命中,两者叠加产出 `"X社区社区"`(双写)。`"村民委员会"→"村"` 作用于 `"X社区村民委员会"` 产出 `"X社区村"`。
- **触发条件**: 任何形如 `"社区…委员会"` 或 `"社区…村委员会"` 的村名(约占 villages.csv 620k 行中的 28k 行)。
- **可观测影响**: 实测 24,853 条 COMMUNITY 词典条目含 `"社区社区"`,3,805 条含 `"社区村"`,均 freq=800。占 COMMUNITY 词典(252,628 条)约 11% 是**永远不会匹配真实输入的垃圾条目**。

### N8 · `_build_bare_name_table` 只加载省/市裸名,区/镇裸名缺失
- **位置**: `org/recognizer.py:148-182` (`_build_bare_name_table`) + `org/recognizer.py:91-99` (trie 构建默认 ROAD)
- **故障**: `_build_bare_name_table` 仅从 `provinces.csv` 和 `cities.csv` 加载裸名。区/镇级裸名(如"朝阳"、"古城"、"向阳"、"新城")不在表中。`_build_trie` 中,无 admin 后缀匹配且不在 `bare_name_type` 的 d1_freqs 词**默认标为 `SegType.ROAD`**。
- **触发条件**: 任何本身是裸区/镇名、无后缀的 d1_freqs 条目。
- **可观测影响**: 8,121 / 63,750 (13%) 的 `org_v1.1.2.pkl` d1_freqs 被误标为 ROAD 而非 DISTRICT/TOWN。例:常熟、永安、高港、向阳、天涯、古城、龙口、诸暨、新城。误标**跨迭代累积**——训练时按 ROAD 计数,后续迭代基于错误统计。

### N9 · `find_suffix_boundaries` sort 缺 seg_type,tie-break 不确定
- **位置**: `core/suffix_matcher.py:30`
- **故障**: sort key 为 `(end, -len(sfx))`,**不含 seg_type**。当两个后缀 end 相同且长度相同时,由 set 迭代顺序决定胜者。Python 的 set 迭代顺序受 `PYTHONHASHSEED` 影响,跨运行/跨版本**非确定**。
- **触发条件**: 两个不同类型、相同 end、相同长度的后缀重叠(如同位置的同字后缀分属 CITY 和 DISTRICT)。
- **可观测影响**: 14 对 ROAD 内部重叠(`路`/`东路`等同类型)目前碰巧正确,但跨类型的 tied 情况会因 hash seed 翻转分类。属潜在不稳定性。

---

## 3. Medium (8 条)

### N10 · confidence 用累计路径代价,非段代价
- **位置**: `loc/recognizer.py:306` + `org/recognizer.py:416`
- **故障**: `confidence = 1.0/(1.0+cost)`,其中 `cost = dp[pos][0]` 是从起点到 pos 的**全部** word+transition 代价之和。同一词典词因位置不同得到差异巨大的 confidence。
- **触发条件**: 任何多段输入。
- **可观测影响**: `北京市` 单独 conf=0.40;作第 2 段 conf=0.125;作第 3 段 conf=0.13。6 段地址中 confidence 单调递减 0.67→0.50→0.24→0.17→0.09→0.06。后段质量再高也因位置被压。`eval.py` 据此打分会误导。

### N11 · org 重建源文件 `org_corpus.csv` 不存在
- **位置**: `tools/org_launch.py:9`
- **故障**: `SOURCE = os.path.join(DATA_DIR, "org_corpus.csv")`,该文件不存在。实际只有 `公司名input.txt`(1.2GB,单列名字格式),与 chunk 期望的 6 列 CSV (`dict,poi,idf,tag,ner,moe`) 格式不同。
- **触发条件**: 删除 `data/split/org/` 后执行 `python tools/org_launch.py all`。
- **可观测影响**: `FileNotFoundError` 阻断 org 重建。现有 `org_v1.1.2.pkl` 锁死在历史语料快照,**不可复现**。

### N12 · `_cleanup_poi_entries` 误删合法 POI 后缀
- **位置**: `loc/builder.py:144-153`
- **故障**: `_cleanup_poi_entries` 删除任何含多字符 admin 后缀(`{自治区,自治州,自治县,街道,民族乡,苏木,办事处,社区,居委会,小区,大街,大道,…}`)的 POI 条目。但 `办事处` 和 `小区` 在 `dicts/poi_suffix_category.csv` 中是**合法 POI 后缀**(类别分别为 `政府` 和 `住宅`)。
- **触发条件**: `b.cleanup()` 执行时。
- **可观测影响**: LOC 词典 POI 部分缺 `办事处`/`小区` 两类。识别时只能走高代价的 `_find_admin_patterns` 路径,且 TOWN/COMMUNITY pattern 优先级会抢先。

### N13 · `split_file` 源缺失时留下空 chunk,自投毒
- **位置**: `tools/pipeline_base.py:32-43`
- **故障**: `split_file` 先 open `num_chunks` 个写句柄,**再** open 源文件。源文件 `FileNotFoundError` 时,16 个空 chunk 文件已留在磁盘。
- **触发条件**: 任何 `split_file` 调用且源不存在(如 org_corpus.csv 缺失、poi_deduped.txt 缺失)。
- **可观测影响**: 下次 `poi_launch.py:41` 的 `chunks_exist = os.path.exists(... "chunk_00.csv")` 返回 True → 跳过 dedup+split → 在空/垃圾 chunk 上训练。**自投毒循环**。

### N14 · d444 malformed 行绕过质量过滤
- **位置**: `tools/org_aggregate.py:30-37, 40-48`
- **故障**: `load_d444_quality` 逐行 `except (ValueError, KeyError)` 捕获后置 `com=org=loc=0`。随后 `is_good_d4_suffix` 检查 `q.get("loc",0) > q.get("org",0)` → `0 > 0 == False` → **反向通过**质量过滤。
- **触发条件**: d444 行的 `com`/`org`/`loc` 字段为非整数字符串(如 `""`、`"N/A"`)。
- **可观测影响**: 无可解析质量数据的后缀**反向通过** `loc>org` 拒绝,进入 `org_v*.pkl` 的 d4 词典。静默质量退化。

### N15 · `split_file` chunk 分配 off-by-one
- **位置**: `tools/pipeline_base.py:28`
- **故障**: `per = total // num_chunks + 1` 是 `floor + 1` 而非 `ceil`。`chunk_id = min(i // per, num_chunks - 1)`。当 `total ≤ (num_chunks-1)·per` 时,尾部 chunk 得 0 行。
- **触发条件**: 小语料 split。如 `total=17, num_chunks=16` → `per=2` → chunk 9-15 空;`total=16` → `per=2` → chunk 8-15 空。
- **可观测影响**: 当前 ~10M 行语料不触发(per≈600k 全填),但小语料/测试场景下尾部空 chunk。

### N16 · `classify_suffix` 17 个单字后缀系统性误判
- **位置**: `loc/importer.py:21-25` + `core/types.py:84-87` (POI_SUFFIX_MAP)
- **故障**: POI_SUFFIX_MAP 含 17 个单字 key(`会/厂/园/城/委/寺/局/店/庙/庭/所/站/苑/行/部/铺/阁`)。`classify_suffix` 以 `endswith` 匹配,任何以此单字结尾的字符串都被归入对应类别。
- **触发条件**: 任何以这 17 字之一结尾的字符串。
- **可观测影响**: 实测 `classify_suffix("测试会")=="政府"`、`classify_suffix("产品委")=="政府"`、`classify_suffix("某某厂")=="工业"`。系统性假阳性泄漏进所有 org/loc 的 POI 段 `poi_type` 元数据。

### N17 · short-d4 惩罚影响 57% d4 条目却零测试
- **位置**: `org/recognizer.py:396-397`
- **故障**: `2≤width≤3 and freq<50000 and end<n*0.8` 的短词 d4 惩罚分支,实测命中 5436/9597 (57%) 的 d4 词典条目。但**无任何测试** toggle `disable_short_d4_penalty=True/False` 验证分支差异。
- **可观测影响**: 单条件打错(如 `freq` 阈值、`<` vs `<=`)会让全部短 POI 过罚或过收,而测试全绿。当前不知道分支是否真在生效。

---

## 4. Low (7 条)

### N18 · 空品牌模型返回 1.0(最大值)
- **位置**: `brand/model.py:88, 91-106` (`brand_score` 空模型分支)
- **故障**: `total_bigrams==0` 时,OOV 分支 line 88 每个 bigram prob=`1.0/(0+1)=1.0`,全过 `1e-12` 阈值,`total_log=0`,`avg_log=0`,`exp(0)=1.0`。`OrgDPRecognizer.brand_score:37` 只检 `is None`,空但已加载的 pkl 绕过 0.5 兜底。
- **触发条件**: 模型 pkl 存在但 `total_bigrams==0`(save 前未 train、损坏/截断 pkl、dev 环境跳过 brand 构建)。
- **可观测影响**: 空模型对**所有**输入返回 1.0(理论最大),与"无模型→中性 0.5"的设计意图相反。
- **与 v1 关系**: **与 v1 L15 关联**。L15 指出 `pipeline.py` 的 brand 属性类内从不调用——经核实属实。因此 N18 当前是 **dormant(潜伏)** 状态:线上无人调 `brand_score`,实际影响为零。但一旦有人启用 brand 串联(v1.3 计划),N18 立即激活。**严重性应被 L15 降级标注**。

### N19 · bigram_prob 平滑公式 in-vocab 与 OOV 不一致
- **位置**: `brand/model.py:87-89`
- **故障**: in-vocab (line 89): `(count_pair + smooth) / (count_ch1 + smooth * len(unigram_counts))`——标准 Add-k,分母用 V。OOV (line 88): `1.0 / (total_bigrams + smooth)`——分母用 `total_bigrams`。真实语料 `total_bigrams ≫ V`,OOV prob 远小于 in-vocab 基线,常跌破 `1e-12` 阈值被 `brand_score` 跳过。
- **触发条件**: 任何含 OOV 字符(不在 `unigram_counts`)的文本。
- **可观测影响**: OOV bigram 被静默忽略,`brand_score` 偏向 in-vocab 字符。OOV 多的文本分数基于子集 bigram。
- **与 v1 关系**: v1 L9 指出 `brand_score` 与 `log_brand_score` 代码重复——那是调用层重复。N19 是底层 `bigram_prob` 公式不一致,不同问题,不冲突。

### N20 · eval.py 默认词典版本 v1.1.1,落后于 config v1.1.2
- **位置**: `eval.py:20`
- **故障**: `VERSION = os.environ.get("DICT_VERSION", "loc_v1.1.1")` 默认 v1.1.1,而 `core/config.py:VERSION="v1.1.2"`。
- **触发条件**: 不带环境变量执行 `python eval.py`。
- **可观测影响**: eval 报告基于旧词典 v1.1.1 的指标,不反映生产词典 v1.1.2。质量评分失真。
- **与 v1 关系**: v1 M11 修了 `run.py` docstring vs VERSION 不一致——那是 run.py。N20 是 eval.py 不同文件,同类问题,不冲突。

### N21 · LOC 与 ORG 的 d4 质量过滤不对称(未文档化)
- **位置**: `loc/builder.py:94` vs `tools/org_aggregate.py:40-55`
- **故障**: `build_from_d444` (LOC) 接受所有 `tf1≥10` 且 `len≥2` 的 d4(**无质量过滤**)。`org_aggregate.is_good_d4_suffix` (ORG) 额外要求 `loc ≤ org` 且 `not in MANUAL_EXCLUDE_D4`。
- **可观测影响**: LOC 词典 d4 有 23,524 条 vs ORG d4 的 9,597 条。LOC 含地理主导后缀(`景区`、`山庄` 等),纯 POI 文本喂 loc 识别器会假阳性。差异未文档化。

### N22 · 77 测试含 6 琐碎 + 11 弱断言 + 2 误导性;60+ DP 转移零覆盖
- **位置**: `tests/` (全目录)
- **故障**:
  - `test_config.py` 6 条全为常量等值断言,零业务逻辑。
  - 11 条只断言"不崩"或部分子串(如 `test_recognize_returns_three_keys` 只查 dict key 存在;`test_orientation_in_address` 名为测方位却不断言任何 ORIENTATION 段)。
  - 2 条误导:`test_brand_score_single_char` 把魔法常量 0.3 当行为契约 codify;`test_empty_text` 同义反复。
  - `loc/recognizer.py` 与 `org/recognizer.py` 的 `_build_transition_costs` 合计 60+ 条转移代价,**0 条单测**。单个值打错不会被发现。
- **可观测影响**: 测试通过不等于行为正确。N5 这种线上 bug 被测试套件完全漏掉。
- **与 v1 关系**: **与 v1 #17(添加单元测试,已标完成)半冲突**。v1 认为加测试已完成(77 条),N22 审查发现数量达标但质量不过。这是对 v1"修复完成"判断的修订:测试**存在**不等于测试**充分**。

### N23 · v1.1.1→v1.1.2 词典 diff 无自动化回归
- **位置**: 无对应文件(HANDOVER.md:114 是一次性手测)
- **故障**: HANDOVER.md:114 的 "loc 0/2000, org 0/500, poi 4/500" 词典稳定性声明是**一次性手测**。`eval.py` 不被任何测试调用,无 `test_eval.py` 或 `test_dict_diff.py`。
- **可观测影响**: 下次词典重建可能大幅漂移而测试全绿。词典稳定性契约无机器保障。

### N24 · 3 处 `pickle.load` 损坏 pkl 无类型化处理
- **位置**: `loc/builder.py:200`、`org/recognizer.py:75`、`brand/model.py:137`
- **故障**: 三处 `pickle.load` 遇损坏文件直接抛 `pickle.UnpicklingError`,无 try/except、无类型化错误、无测试。
- **可观测影响**: 损坏 pkl 产生不友好堆栈,无诊断信息。
- **与 v1 关系**: v1 H5 修了 `org/recognizer.py:195` 的 bare except——那是 CSV 读取方向。N24 是 pickle 方向的**相反问题**(完全无 try),不同性质,不冲突。

---

## 5. 合并清单 (二代 24 条 + v1.0 剩余 15 条 = 39 条)

> 来源标注:`[新]` = 二代新发现,`[v1]` = v1.0 遗留未修

### Critical (5 条,全新)

| # | 来源 | 位置 | 摘要 |
|---|---|---|---|
| N1 | 新 | `loc/recognizer.py:396` | `_cleanup_chars` 死代码,停用字过滤永不执行 |
| N2 | 新 | `org/recognizer.py:441-452` | `TRAILING_SINGLE` 合并死代码 |
| N3 | 新 | `tools/poi_launch.py:10` + `poi_dedup.py:44` | POI 重建产出空词典 |
| N4 | 新 | `tools/org_chunk_stats.py:65` | 参数顺序写反,迭代精炼失效 |
| N5 | 新 | `pipeline.py:42-46` | poi_dict 参数被丢弃,线上加载错版本 |

### High (4 新 + 0 v1)

| # | 来源 | 位置 | 摘要 |
|---|---|---|---|
| N6 | 新 | `loc/recognizer.py:228-234` | pattern span 含夹带垃圾 |
| N7 | 新 | `loc/importer.py:11-36` | 村名标准化模式覆盖,产"社区社区" |
| N8 | 新 | `org/recognizer.py:148-182` | 裸名表只加载省市,13% 误标 ROAD |
| N9 | 新 | `core/suffix_matcher.py:30` | tie-break 缺 seg_type,非确定 |

> v1.0 的 High (H1-H8) 已在 v1.2.2 全部修复,无遗留。

### Medium (8 新 + 8 v1)

| # | 来源 | 位置 | 摘要 |
|---|---|---|---|
| N10 | 新 | `loc/recognizer.py:306` + `org/recognizer.py:416` | confidence 用累计代价 |
| N11 | 新 | `tools/org_launch.py:9` | org_corpus.csv 不存在 |
| N12 | 新 | `loc/builder.py:144-153` | 误删合法 POI 后缀 |
| N13 | 新 | `tools/pipeline_base.py:32-43` | split_file 留空 chunk 自投毒 |
| N14 | 新 | `tools/org_aggregate.py:30-48` | d444 malformed 行绕过过滤 |
| N15 | 新 | `tools/pipeline_base.py:28` | split_file 分配 off-by-one |
| N16 | 新 | `loc/importer.py:21-25` | 17 单字后缀系统性误判 |
| N17 | 新 | `org/recognizer.py:396-397` | short-d4 惩罚零测试 |
| M2 | v1 | `loc/builder.py` + `loc/importer.py` | 40+ 魔法数字 |
| M4 | v1 | `org/recognizer.py:272-337` | 转移代价表魔法数字 |
| M5 | v1 | `core/types.py:62` | LOCATION_SUFFIX_MAP 是 set 命名 _MAP |
| M6 | v1 | `core/types.py:20` | SegType.BRAND 枚举未用 |
| M7 | v1 | `loc/builder.py:12/184` | __init__ vs load() 版本默认不一致 |
| M12 | v1 | `pipeline.py:25-54` | brand hasattr vs loc/org/poi None 不一致 |
| M13 | v1 | `brand/model.py:27,60` | CSV 列名硬编码 |
| M16 | v1 | `loc/recognizer.py:394` | 方法内懒加载 import |

### Low (7 新 + 7 v1)

| # | 来源 | 位置 | 摘要 |
|---|---|---|---|
| N18 | 新 | `brand/model.py:88` | 空模型返回 1.0 |
| N19 | 新 | `brand/model.py:87-89` | 平滑公式不一致 |
| N20 | 新 | `eval.py:20` | eval 默认版本落后 |
| N21 | 新 | `loc/builder.py:94` vs `org_aggregate.py:40` | d4 过滤不对称 |
| N22 | 新 | `tests/` | 测试质量低 |
| N23 | 新 | 无文件 | 词典 diff 无回归 |
| N24 | 新 | 3 处 pickle.load | 损坏 pkl 无处理 |
| L1 | v1 | 全局 ~72 处 | print vs logging |
| L9 | v1 | `brand/model.py` | brand_score/log_brand_score 重复 |
| L11 | v1 | `brand/model.py` | smooth 命名不当 |
| L12 | v1 | 4 个 `__init__.py` | 无公开 API 导出 |
| L15 | v1 | `pipeline.py` | brand 属性类内未调用 |
| L16 | v1 | `poi/recognizer.py` | recognize 缺返回类型 |
| L17 | v1 | `eval.py` | 评分权重 1.5/0.5 无文档 |

---

## 6. 与 v1.0 口径修正

v1.0 概要 `00_审计概要_v1.0.md:7,47` 称 "37/50 已修复"。二代逐条核对 `02_问题清单_v1.0.md` 实际为 **35/50 已修复,剩 15 条**(概要少算 2 条)。本报告采用 15 条为准。

---

## 7. 测试质量专项评估

77 条用例全过是**虚假绿灯**。核心问题:

1. **断言层级浅**:多测试只查"返回了 dict""段数>0""类型是 SegType"这类同义反复,不断言具体段文本、边界、poi_type。
2. **关键路径零覆盖**:loc/org 的 `_build_transition_costs` 共 60+ 条转移,0 条单测。单个代价打错不会被发现。
3. **线上 bug 漏网**:N5 (poi_dict 被丢弃) 线上就在错,无任何测试断言 `pipe.poi._rec._dict_name`。
4. **误导性测试**:`test_brand_score_single_char` 把魔法常量 0.3 当行为契约 codify,实际是"测常量没变"而非"测行为正确"。
5. **无回归自动化**:HANDOVER.md 的词典 diff 声明是一次性手测,`eval.py` 不被测试调用。
6. **脆弱依赖**:15 条测试用真实词典做精确段断言,词典重建(v1.1.3)即崩——这是有用的回归信号但需文档化。

---

## 8. 二代新发现与 v1 遗留的冲突/关联分析

| 二代项 | v1 项 | 关系 | 说明 |
|---|---|---|---|
| N1 (`_cleanup_chars` 死代码) | M17 (已修 end 算术) | **同位不同层** | M17 修了死代码里的算术。修复有效(若 N1 修复让分支可达,M17 算术仍需保留),但单看 M17 是无效修复。**不冲突,N1 是 M17 的必要补充**。 |
| N18 (空模型返回 1.0) | L15 (brand 属性未调用) | **降级关联** | L15 核实属实——brand 类内从不调用。因此 N18 当前 dormant,线上影响为零。但启用 brand 串联即激活。**N18 严重性应被 L15 降级标注:当前潜伏,启用即 Critical**。 |
| N22 (测试质量低) | v1 #17 (加测试已标完成) | **修订判断** | v1 标 #17 完成是基于"77 条用例通过"。N22 审查发现数量达标、质量不过。**这是对 v1 修复完成判断的修订,非冲突**。 |
| N3 (POI 空词典) | H6 (poi_dedup 导入副作用已修) | **同位不同层** | H6 修了导入时 IO,N3 是源文件缺失时静默 SKIP 继续写空。不同问题,不冲突。 |
| N4 (org_chunk_stats 参数顺序) | H8 (poi_launch 版本不一致已修) | **不同文件** | H8 修 poi_launch,N4 是 org_chunk_stats。同类问题不同位置,不冲突。 |
| N24 (pickle 无处理) | H5 (bare except 已修) | **相反方向** | H5 修了过度捕获,N24 是完全无捕获。不同性质,不冲突。 |
| N9 (suffix_matcher tie-break) | H2/M5 (后缀合并已重构/命名) | **不同层** | H2 修了重复逻辑,M5 是命名。N9 是新代码 sort key 缺字段。不冲突。 |
| 其余 17 条 | — | **独立** | 与 v1 遗留无关联。 |

**结论**:24 条新发现与 15 条 v1 遗留**无真冲突**。3 处关联(N1↔M17、N18↔L15、N22↔#17)需在修复时协同处理,避免单修一侧留下漏洞。

---

## 9. 附录:验证方法

- N1/N2/N5/N6/N7/N9/N10/N16/N18:运行时探测(构造输入、调用函数、断言输出)
- N3/N4/N8/N11/N12/N13/N14/N15/N20/N21:源码核对 + 文件存在性 + 词典条目计数
- N17/N22/N23/N24:测试目录 grep + 覆盖矩阵手工填充
- N19:公式推导 + toy model 数值验证

所有验证为只读,未修改任何文件。
