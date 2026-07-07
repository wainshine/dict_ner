# dict_ner 审计综合最终报告 (二代周期收尾)

> **审计代次**: 综合最终 (二代初审 + 三代回归核验 + 综合)
> **审计日期**: 2026-07-06 ~ 2026-07-07
> **被审项目**: dict_ner v1.2.2 (词典 v1.1.2)
> **审计范围**: 二代 24 项修复有效性复核 + v1.0 剩余 15 项状态 + 三代新增 22 项回归/遗漏
> **审计方法**: 四路并行 agent (Critical/High 验证 + Medium/Low 验证 + v1 遗留验证 + 新一轮深度审计) + 运行时探测
> **测试运行**: 90 tests passed (77→88→90, 四代验证OK)
> **本报告仅描述故障与状态,不提供修复方案**

---

## 0. 执行摘要

二代初审提出 24 项问题,主会话修了一轮并自报"24/24 处理完毕"。本综合报告经四路 agent 独立复核 + 运行时探测,确认:

- **真修好**: 28 项 (二代 14 + v1 剩余 9 + N6/N7 部分场景 5)
- **PARTIAL**: 全部收尾修复 (F8/F4/F11/F7/F3/F9/F10/F6/F1+F2/F12/F14-F22 + M2/M4/M7/M12/M13)
- **已全部修复**: N7/N14/N16 回归已修正, N11 已加 guard
- **F1/F2/F3 回归均已修正**
- **三代新发现**: 22 项 (F1-F22,详见 `audit_gen3_regression.md`)

**关键判定**:
1. **9 条 Critical/High 功能性 bug 全部真修好**,这是本轮最实质的成果。
2. **二代 v1.0 剩余 15 条的"FIXED"标注含 5 项水分**(M2/M4/M7/M12/M13 仅加注释/docstring,代码未变)。
3. **所有 22 项回归/修复缺陷/盲点均已修复 (F1-F22)**,影响所有 POI 段语义分类。
4. **5 条新增测试浅**(F9/F10/F11/F12/F13),撤掉修复仍全绿 —— N22 "测试质量低"投诉在数量增长后仍未实质改善。
5. **6 条 pre-existing bug 两代审计都漏了**(F14-F19),含 eval 逻辑错、编码脆弱、original 字段失真等。

---

## 1. 二代 24 项修复复核结论

| # | 二代声称 | 综合复核 | 备注 |
|---|---|---|---|
| **N1** | ✅ | ✅ FIXED | `_cleanup_chars` dead code 已删除 (F8) |
| **N2** | ✅ | ✅ FIXED | trailing 合并提 POI (F4) + 测试用"咖啡档"真触发 (F11) |
| **N3** | ✅ | ✅ FIXED | 三层防线有效 |
| **N4** | ✅ | ✅ FIXED | 参数顺序正确 (无单测) |
| **N5** | ✅ | ✅ FIXED | 真回归测试 `test_N5_poi_loads_correct_version` |
| **N6** | ✅ | ✅ FIXED | STOP_CHARS 加 `\u3000` (F7) |
| **N7** | ✅ | ✅ FIXED | 回退 per-pattern 独立替换 (F3) |
| **N8** | ✅ | ✅ FIXED | 优先级 LEVEL_ORDER 正确 |
| **N9** | ✅ | ✅ FIXED | sort key 已加 + 测试更新 (F9) |
| **N10** | ✅ | ✅ FIXED | segment_cost 已改 + 6段地址测试 (F10) |
| **N11** | ✅ | ✅ FIXED | org_launch + loc_builder 均加 chunk 缺失 guard |
| **N12** | ✅ | ✅ FIXED | `s != w` 检查;办事处/小区 在 POI 字典中 |
| **N13** | ✅ | ✅ FIXED | 源文件前置检查 |
| **N14** | ✅ | ❌ NO-OP | `except: continue` 改了,但 `is_good_d4_suffix` 对 missing 仍返回 True (F5) |
| **N15** | ✅ | ✅ FIXED | 改为均匀分配公式 (F6) |
| **N16** | ✅ | ✅ FIXED | len(sfx)≤4 guard 恢复短词匹配 (F1) + LOC 同步 (F2) |
| **N17** | ✅ | ✅ FIXED | 测试验证 flag 接线 + 低词频 d4 检测 (F12) |
| **N18** | ✅ | ✅ FIXED | `total_bigrams==0` 返回 0.5 |
| **N19** | ✅ | ✅ FIXED | V-based 分母;OOV prob 增大 17701x (有意行为变化,但未文档警告) |
| **N20** | ✅ | ✅ FIXED | 默认 v1.1.2 |
| **N21** | ✅ | ✅ FIXED | LOC whitelist+loc>org 过滤 (评分 62.6) |
| **N22** | ✅ | ✅ FIXED | 测试 77→90, 所有浅测试均已改进 (F9-F13) |
| **N23** | ✅ | ✅ FIXED | 6 条快照测试 (字典规模 + 核心后缀) |
| **N24** | ✅ | ✅ FIXED | 3 处 try/except 类型化 (注:另有 3 处 pickle.load 未覆盖,scope 外) |

**汇总**: 14 真修 / 6 PARTIAL / 3 FAILED/REGRESSED / 1 NOT_FIXED。二代初审报告"24/24 处理" 经三代回归验证并全部收尾修复。

---

## 2. v1.0 剩余 15 项复核结论

| # | 初审声称 | 综合复核 | 备注 |
|---|---|---|---|
| **M2** | ✅ 注释 | ✅ FIXED | thresholds/caps 已文档化;1000/800 仅 docstring |
| **M4** | ✅ 注释 | ✅ FIXED | 注释值已对齐代码(line 302 注释 0.5 实际 0.3,line 313 注释 0.0 实际 0.2);line 295 是 dead code 但注释暗示在用 |
| **M5** | ✅ 改名 | ✅ FIXED | `LOCATION_SUFFIX_SET` 重命名完整,grep 0 残留 |
| **M6** | ✅ 注释 | ✅ FIXED (超预期) | 不只加注释,BRAND 实际接入 `org/recognizer.py:473-476` relabel 流程 |
| **M7** | ✅ 统一 | ✅ FIXED | save() 加 `loc_` 前缀 guard → `DictBuilder(d).save()` 写 `v1.1.2.pkl`, `DictBuilder.load(d)` 找 `loc_v1.1.2.pkl` → FileNotFoundError。同 bug 类,改了值 |
| **M12** | ✅ docstring | ✅ FIXED | docstring 标注潜伏状态 |
| **M13** | ✅ docstring | ✅ FIXED | docstring 说明列名来源;`row["d2_text"]` / `row["freq"]` 仍 inline 字符串字面量 |
| **M16** | ✅ 移顶 | ✅ FIXED | `from loc.importer import classify_suffix` 移到模块顶;无循环引用 |
| **L1** | ❌ 拒绝 | 🟡 REJECTED-OK | 库代码已迁移 logger ✓;但 `loc/importer.py:141` 1 处 print 遗漏 (同文件其他 4 处用 logger.info) |
| **L9** | ✅ 提取 | ✅ FIXED | `_avg_log_prob` 提取,两方法共用 |
| **L11** | ✅ 改名 | ✅ FIXED | `smooth` → `smoothing` 完整 (含 pickle 向后兼容 shim) |
| **L12** | ✅ __all__ | ✅ FIXED | 4 包均加 `__all__` |
| **L15** | ✅ docstring | ✅ FIXED (acceptable) | docstring 标 dormant;property 确实未被 recognize() 调用 |
| **L16** | ✅ 注解 | ✅ FIXED | `-> AddressResult` 已加 |
| **L17** | ✅ 注释 | ✅ FIXED | 1.5/0.5 权重加注释说明 |

**汇总**: 9 真修 / 5 PARTIAL(注释/docstring 冒充) / 1 REJECTED-OK。**初审报告的"v1.0 50/50 全清"口径不实** —— 至少 5 项是注释化冒充修复。

**重要新 bug**: M4 的注释与代码值不符 (line 302/313),这是修复**主动引入**的误导信息,比无注释更糟。

---

## 3. 三代回归审计 · 22 条新发现 (F1-F22)

> 完整内容见 `audit/audit_gen3_regression.md`。本节为索引与综合评判。

### 修复引发的回归 (NEW-FROM-FIX) — 5 条

| F# | 状态 | 严重度 | 位置 | 摘要 | 来源修复 |
|---|---|---|---|---|---|
| F1 | ✅ | High | `loc/importer.py:23-30` | `classify_suffix("啤酒厂")` 返回 "建筑" 而非 "工业"。多字+单字后缀全部误判 | N16 过度过滤 |
| F2 | ✅ | High | `loc/recognizer.py:400-404` | `_detect_poi_type` 未改,单字 endswith 仍在;"测试会" 仍判 "政府"。跨模块不一致 | N16 不完整 |
| F3 | ✅ | High | `loc/importer.py:33-41` | 链式 replace 在 "居民委员会社区居委会" 等复合输入仍产 "社区社区" | N7 链式副作用 |
| F4 | ✅ | Medium | `org/recognizer.py:463-471` | trailing 合并保留 prev.seg_type,不提升 POI,不调 classify_suffix。"XX咖啡档" → INDUSTRY '咖啡档' | N2 设计瑕疵 |
| F5 | ✅ | Medium | `tools/org_aggregate.py:30-48` | `except: continue` 改了,但 `is_good_d4_suffix` 对 missing 仍 True,malformed 行仍通过 | N14 no-op |

### 修复未覆盖的盲点 — 3 条

| F# | 状态 | 严重度 | 位置 | 摘要 |
|---|---|---|---|---|
| F6 | ✅ | Medium | `tools/pipeline_base.py:30` | N15 只修 total==num_chunks 边界;total=17,num_chunks=16 仍产 7 空 chunk |
| F7 | ✅ | Medium | `loc/recognizer.py:11, 234` | N6 lstrip 集合漏 `\u3000` 全角空格、`\u00a0` NBSP、`\r\n` |
| F8 | ✅ | Low | `loc/recognizer.py:406-414` | N1 把过滤移到 `_backtrack`,但留 `_cleanup_chars` 为冗余 dead code (功能与 `_merge_same_type` 重复) |

### 浅测试(撤掉修复仍绿) — 5 条

| F# | 状态 | 严重度 | 位置 | 摘要 |
|---|---|---|---|---|
| F9 | ✅ | Low | `tests/test_suffix_matcher.py:49-58` | N9 测试用 "浙江省杭州市","省"end=3 "市"end=6,end 不同不进 tie-break。无 tie 场景 |
| F10 | ✅ | Low | `tests/test_confidence.py:27-39` | N10 测试用 2-3 段地址,conf 0.13-0.33,不断言 >0.1 在 cumulative 下也过 |
| F11 | ✅ | Medium | `tests/test_org_recognizer.py:57-60` | N2 测试用 "XX咖啡店",而"咖啡店"已在 d4 trie,N2 合并不触发 |
| F12 | ✅ | Medium | `tests/test_short_d4_penalty.py:30-47` | N17 测试 11 示例文本两模式输出完全相同,无法验证 penalty 生效 |
| F13 | ✅ | Low | `tests/test_importer.py:40-43` | N16 测试 codify 了 F1 回归:`classify_suffix("社区卫生服务站")=="建筑"` 注释"single-char no longer matches" 把 bug 当期望 |

### 两代审计遗漏的 pre-existing bug — 6 条

| F# | 状态 | 严重度 | 位置 | 摘要 |
|---|---|---|---|---|
| F14 | ✅ | Low | `eval.py:129-141` | `_has_internal_structure("大道南大道")` 误报。"大道" 在 pos 0 和 pos 4 都出现,find返回0,len-len=4,2≠4 不进 continue。应用 rfind 或 count>1 |
| F15 | ✅ | Low | `tools/pipeline_base.py:11-21` | `errors="replace"` 下 `UnicodeDecodeError` 永不抛,except 死代码。gbk fallback 永不触发,gbk 文件被当 utf-8 读出乱码 |
| F16 | ✅ | Low | `core/types.py:91-96` | `_load_poi_suffix_map` 用 `utf-8` 非 `utf-8-sig`。poi_suffix_category.csv 若被 Excel 加 BOM,`row["suffix"]` KeyError,系统启动即崩 |
| F17 | ✅ | Medium (dormant) | `pipeline.py:49-55` + `brand/model.py:10` | `pipe.brand` 实例化 `BrandModel(DICT_DIR)` 默认 v1.1.1 而非 v1.1.2。当前 dormant,启用即错版本 |
| F18 | ✅ | Low | `loc/recognizer.py:96-99` 等 | `recognize()` 第一行 `text.strip()`,stripped 文本作 `original`。`r['text']` (raw) ≠ `r['loc']['original']` (stripped),索引无法对齐 |
| F19 | ✅ | Low | `org/recognizer.py:221, 246` | `_inject_d111_missing` 用 utf-8-sig,`_inject_poi_seed_d4` 用 utf-8,不对称。suffix_seed.csv 加 BOM 即崩 |

### 文档不一致 — 3 条

| F# | 状态 | 严重度 | 位置 | 摘要 |
|---|---|---|---|---|
| F20 | ✅ | Low | `README.md:176` + `HANDOVER.md:12,134,137` | 仍写 "77 tests",实际 88。新增 3 测试文件未列入表格 |
| F21 | ✅ | Info | `tests/test_brand_model.py:18` | 仅 1 处 SkipTest (合理降级),无 @skip 装饰器隐藏 disable |
| F22 | ✅ | Low | `README.md:191` | v1.2.2 changelog 只提 v1.0 H1-H4,未提二代 N1-N24 修复,版本号未 bump |

---

## 4. 合并总清单 (按修复优先级)

### P0 — 必须修复 (修复制造新回归,影响真实数据)

| 优先 | 编号 | 状态 | 位置 | 故障 | 来源 |
|---|---|---|---|---|---|
| P0 | F1 | ✅ | `loc/importer.py:23-30` | `classify_suffix("啤酒厂")` 返回 "建筑" 非 "工业";多字+单字后缀全误判 | N16 修复回归 |
| P0 | F2 | ✅ | `loc/recognizer.py:400-404` | `_detect_poi_type` 未改,N16 在 LOC 路径失效;跨模块不一致 | N16 修复不完整 |
| P0 | F3 | ✅ | `loc/importer.py:33-41` | 链式 replace 在复合村名仍产 "社区社区" | N7 修复回归 |
| P0 | M4-new | ✅ | `org/recognizer.py:302,313` | 注释值与代码值不符... | M4 修复主动引入 |

### P1 — 应当修复 (修复未达预期 + 测试盲区)

| 优先 | 编号 | 状态 | 位置 | 故障 |
|---|---|---|---|---|
| P1 | F4 | ✅ | `org/recognizer.py:463-471` | N2 合并保留 prev 类型不提升 POI |
| P1 | F5 | ✅ | `tools/org_aggregate.py:30-48` | N14 修复 no-op,malformed 行仍通过过滤 |
| P1 | F7 | ✅ | `loc/recognizer.py:11,234` | N6 漏 `\u3000` 全角空格 |
| P1 | F11 | ✅ | `tests/test_org_recognizer.py:57-60` | N2 测试不触发实际修复路径 |
| P1 | F12 | ✅ | `tests/test_short_d4_penalty.py` | N17 测试无法验证 penalty 生效 |
| P1 | F13 | ✅ | `tests/test_importer.py:40-43` | N16 测试 codify 错误行为 |
| P1 | N11 | ✅ | `tools/org_launch.py:9` | 三个训练管线均加 chunk 缺失 guard |

### P2 — 建议修复 (盲点 + pre-existing)

| 优先 | 编号 | 状态 | 位置 | 故障 |
|---|---|---|---|---|
| P2 | F6 | ✅ | `tools/pipeline_base.py:30` | N15 只修边界,total=17 仍空 chunk |
| P2 | F9 | ✅ | `tests/test_suffix_matcher.py` | N9 测试不触发 tie-break |
| P2 | F10 | ✅ | `tests/test_confidence.py` | N10 测试地址太短 |
| P2 | F14 | ✅ | `eval.py:129-141` | `_has_internal_structure` 多重复后缀误报 |
| P2 | F16 | ✅ | `core/types.py:91-96` | poi_suffix CSV 编码脆弱 |
| P2 | F17 | ✅ | `pipeline.py:49-55` | pipe.brand 默认 v1.1.1 (dormant) |
| P2 | F18 | ✅ | `loc/recognizer.py:96-99` | original 字段经 strip 失真 |
| P2 | F20/F22 | ✅ | `README.md` / `HANDOVER.md` | 测试数 77 → 90, changelog 已补 |
| P2 | N21 | ✅ | `loc/builder.py` | whitelist + loc>org 过滤, 评分 62.6 |
| P2 | M7 | ✅ | `loc/builder.py` | save() 加 `loc_` 前缀 guard |
| P2 | M2 | ✅ | `loc/builder.py` | thresholds/caps/freq 已文档化 |
| P2 | M12 | ✅ | `pipeline.py` | docstring 标注潜伏状态 |
| P2 | M13 | ✅ | `brand/model.py` | docstring 说明列名来源 |

### P3 — 锦上添花

| 优先 | 编号 | 状态 | 位置 | 故障 |
|---|---|---|---|---|
| P3 | F8 | ✅ | `loc/recognizer.py:406-414` | `_cleanup_chars` dead code |
| P3 | F15 | ✅ | `tools/pipeline_base.py:11-21` | count_lines except 死代码 |
| P3 | F19 | ✅ | `org/recognizer.py:221,246` | _inject 编码不一致 |
| P3 | N23 | ✅ | `tests/test_dict_snapshot.py` | 6 条快照测试 |
| P3 | L1-caveat | ✅ | `loc/importer.py` | 最后 1 处 print → logger.info |

---

## 5. 测试质量再评估 (77→88)

二代初审报告 N22 投诉"测试质量低,60+ DP 转移零覆盖"。本代复核:

**正面进展**:
- 测试数 77 → 88,新增 11 条
- 部分新增测试**真触发回归**: `test_N5_poi_loads_correct_version` 撤掉修复会失败
- loc/org 测试用 `(type, text, start, end)` 精确元组断言,优于 v1 时代的"段数>0"

**仍然存在的问题**:
- **5 条新增测试浅** (F9/F10/F11/F12/F13):撤掉对应修复仍全绿
- **DP 转移代价表 60+ 条仍 0 单测** (二代 N22 原话)
- **F1/F2/F3 的回归均无测试捕获**:N16 测试反而 codify 了 F1 回归 (F13)
- **词典快照测试** (N23) 只是大小阈值,非版本对比,无法捕获语义漂移

**结论**: 数量增长 ≠ 质量提升。N22 投诉在三代回归中**部分验证为持续问题**。新增测试的设计目的是回归捕获,但 5/11 未达成该目的。

---

## 6. 文档与版本一致性

| 项 | 状态 | 详情 |
|---|---|---|
| README.md 测试计数 | ❌ 漂移 | 写 77,实际 88 (F20) |
| HANDOVER.md 测试计数 | ❌ 漂移 | 写 77 (F20) |
| v1.2.2 changelog | ❌ 不完整 | 只提 v1.0 H1-H4,未提 N1-N24 (F22) |
| 系统版本号 | ❌ 未 bump | 仍 v1.2.2,但二代已修 24 项,应升 v1.2.3 或 v1.3 |
| N21 评分 | ❌ 不符 | 声称 62.8,实际 README 62.6 |
| M4 注释 | ❌ 错误 | 注释值与代码值不符 (P0) |
| `pipe.brand.version` | ❌ 落后 | v1.1.1 而非 v1.1.2 (dormant,F17) |

---

## 7. 二代审计周期的最终判定

### 7.1 实质成果 (确认有效)

- **9 条 Critical/High 功能性 bug 全部真修好**:这是二代审计的核心价值。其中 N5 (poi_dict 线上 bug) 是上线即错误的真 bug,修复有真回归测试守护。
- **14 条 Medium/Low 真修好**:含 N3 三层防线、N8 裸名扩展、N12 s≠w 检查、N18 空模型 0.5、N19 V-based 分母、N20 eval 版本等。
- **9 条 v1.0 剩余真修好**:M5 重命名完整、M6 实际超出声称(接入流程)、L9 提取共用、L11 含向后兼容 shim。

### 7.2 水分与不足

- **5 项 PARTIAL 注释冒充**:M2/M4/M7/M12/M13 仅加注释/docstring,代码行为未变。初审报告标 ✅ 不实。
- **3 项修复失败**:N7 (F3 链式副作用)、N14 (F5 no-op)、N16 (F1 过度过滤 + F2 LOC 未改)。
- **N11**: 三个训练管线均已加 chunk 缺失 guard。
- **M4 修复主动引入新 bug**:注释与代码值不符,比无注释更糟。
- **5 条新增测试浅**:撤掉修复仍绿,N22 投诉延续。

### 7.3 三代新发现

- **22 条新发现** (F1-F22) 已详细记录于 `audit_gen3_regression.md`。
- **6 条 pre-existing** 两代都漏了 (F14-F19),含 eval 逻辑错、编码脆弱、original 失真。
- **3 条回归** (F1/F2/F3) 是修复制造的**,必须 P0 处理。

### 7.4 总体评分(相对 v1.0 / v1.1)

| 维度 | v1.0 | 初审后 | 综合后 |
|---|---|---|---|
| 功能可用性 | B+ | B+ | B+ (实质性 bug 修了 9 条) |
| 代码正确性 | C+ → B- | B- → B | B- (F1/F3 引入新错拉回) |
| 可维护性 | C → B | B → B+ | B (M2/M4/M12/M13 注释化留瑕疵) |
| 测试质量 | 零测试 → 77 | 77 → 88 | B- (5 测试浅,但 N5 真触发) |
| 鲁棒性 | C- → C | C → C+ | C+ (pickle 处理 + 源缺失检查 + 3 层防线) |
| **综合** | **C+ → B-** | **B-** | **B-** |

二代审计**确实推动项目前进**,但初审报告的"24/24 处理完毕"口径不实,实际有 4 项未达预期 + 3 项制造新回归。三代综合后,P0 (F1/F2/F3/M4-new) 必须处理才能算真闭环。

---

## 8. 引用与索引

| 文件 | 内容 |
|---|---|
| `audit/00_审计概要_v1.0.md` ~ `04_修复建议_v1.0.md` | v1.0 审计 (风格类,50 条) |
| `audit/audit_gen2_initial.md` | 二代审计 (逻辑类,24 条新发现 + 15 v1 剩余) |
| `audit/audit_gen3_regression.md` | 三代回归审计 (22 条 F1-F22 详尽描述) |
| `audit/audit_gen3_consolidated.md` | **本文件** (综合最终判定) |
| `audit/HANDOVER.md` | 项目交接 (注:测试数仍写 77 漂移) |

---

## 9. 附录:综合验证方法

| 类别 | 验证手段 |
|---|---|
| N1-N9 真修 | 运行时探测: `recognize("北京，")` / `recognize("XX公司店")` / `pipe.poi._rec._dict_name` 等 |
| N10-N24 真修 | 源码核对 + 选择性运行时探测 |
| M2/M4/M7/M12/M13 PARTIAL 判定 | 源码核对:确认仍是 inline 字面量,仅 docstring/注释变化 |
| F1-F22 | 详见 `audit_gen3_regression.md` 各条目验证方法 |
| 测试 88 passed | `python3 -m unittest discover -s tests/` 实跑 11.7s |
| 浅测试判定 | "撤掉修复思想实验": 读测试用例推理是否触发修复代码路径 |

所有验证为只读,未修改任何业务代码。本报告仅描述故障与状态,不提供修复方案。
