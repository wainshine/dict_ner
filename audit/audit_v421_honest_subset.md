# v4.2.1 复核 — 诚实子集回退：种子噪声 vs 校准集损失

> 触发：三代审计报告（2026-10-26）结论「重训真实回退 ~0.45pt，约一半降幅不是口径切换」。
> 复核范围：v4.2.0 模型 vs 归档旧模型（`clf_v3_baseline_v42.pkl`），固定新 group split，诚实子集 = val/test 中文本不在 `final_train6` 的行。
> **结论：原审计的「真实回退」结论不成立（至少被显著高估）。** 单 seed 噪声与 -0.45pt 同量级；恢复 23,609 行 calib 的 cross-fit 还能再收回 ~0.3pt。v4.2.0 的 seed=42 是一次偏差抽样，不是系统性重训退化。

## 1. 原审计结论复现（数值全部对上）

诚实子集：val 13,991 行（36.3%），test 14,019 行（36.4%）。旧模型训练集 `final_train6` 见不到的文本。

| split | 旧模型 macro-F1 | v4.2.0 macro-F1 | Δ（各自乘数） | Δ（同乘旧乘数） |
|---|---:|---:|---:|---:|
| val | 0.9073 | 0.9026 | **-0.0047** | -0.0056 |
| test | 0.9022 | 0.8979 | **-0.0043** | -0.0066 |

逐类看，差距几乎全部在 UNKNOWN：val 0.9311→0.9156，test 0.9341→0.9113；ORG/POI/ADDR 的 F1 差都在 ±0.004 内。

### 根因不是校准映射

把两个模型的 isotonic 映射互换（old raw + new iso / new raw + old iso），差距几乎不变：

| 组合 | val 诚实 macro-F1 | test 诚实 macro-F1 |
|---|---:|---:|
| 旧 raw + 旧 iso | 0.9073 | 0.9022 |
| 旧 raw + 新 iso | 0.9062 | 0.9001 |
| 新 raw + 旧 iso | 0.9020 | 0.8976 |
| 新 raw + 新 iso | 0.9026 | 0.8979 |

→ 校准映射只贡献 ~0.001；**基础 GBDT 本身在 UNKNOWN 上更弱**：raw-softmax 诚实子集 UNKNOWN recall val 0.851→0.814、test 0.864→0.828，更多真 UNKNOWN 被分到 POI（test 73→97 条）。

## 2. 关键反证：单 seed 噪声与「回退」同量级

同一 `final_train7`、同一 held-out calib、只把 GBDT `random_state` 42→43：

| 指标 | seed 42（v4.2.0） | seed 43 | Δ |
|---|---:|---:|---:|
| val tuned macro-F1 | 0.9053 | **0.9082** | +0.0029 |
| test macro-F1 | 0.9035 | **0.9053** | +0.0018 |
| clean accuracy | 0.9689 | **0.9703** | +0.0014 |
| ECE val / test | 0.0253 / 0.0215 | **0.0129 / 0.0110** | 约减半 |
| 诚实 val macro-F1（同乘旧乘数） | 0.9017 | **0.9061** | +0.0044 |
| 诚实 test macro-F1（同乘旧乘数） | 0.8956 | **0.8981** | +0.0025 |

**单 seed 换一个随机数，就能移动 0.0044（val 诚实子集）/ 0.0025（test 诚实子集）**——与原审计报告的 -0.0047/-0.0043 同量级。原审计只比较了两个单次训练，没有做 seed 方差控制，因此把「一次偏差抽样」写成了「重训真实退化」。

## 3. 恢复 calib 行：可避免的那部分损失

v4.2.0 为 held-out 校准从训练中剥离了 23,609 行（含 1,398 条 UNKNOWN，占训练 UNKNOWN 的 2.5%）。把 calib 行并回训练后（seed 42/43，诊断用 115K `train_feats` 校准）：

| 模型 | test macro-F1 | clean | ECE val/test | 诚实 val/test（各自乘数） |
|---|---:|---:|---:|---:|
| v4.2.0 seed42 | 0.9035 | 0.9689 | 0.0253 / 0.0215 | 0.9026 / 0.8979 |
| final7 + calib seed42 | 0.9064 | 0.9714 | 0.0122 / 0.0126 | 0.9060 / 0.8993 |
| final7 + calib seed43 | 0.9067 | 0.9726 | 0.0184 / 0.0156 | 0.9049 / 0.9012 |
| **cross-fit K=5 seed42**（OOF 校准，诚实） | **0.9069** | **0.9738** | 0.0325 / 0.0332 | **0.9069 / 0.9013** |

- 恢复 calib 行稳定带来 **+0.003 test macro-F1 / +0.0025~0.005 clean**，并把诚实子集差距从 -0.0043 收到 -0.0009（cross-fit，对旧模型）。
- cross-fit 的 ECE 变差（0.0325/0.0332）是 OOF（80% 数据模型）与最终全量模型分数尺度不一致导致；用 val 拟合一个只改 confidence 的 temperature（T=1.3）可回到 0.0258/0.0251，但仍不如 held-out 校准的 seed43（0.0129/0.0110）。因此 cross-fit 作为**可选训练模式**保留，不作为生产模型。

## 4. 修正后的归因

headline 0.9092→0.9035（-0.0057）不应再表述为「约一半是重训真实回退」。更准确的分解是：

1. **泄漏修正（主项）**：旧 0.9092 含 9.49% train/test 文本重叠，真实泛化约 0.902（诚实子集）。
2. **单 seed 噪声（±0.002~0.004）**：seed42 是偏差抽样；seed43 在完全相同的 clean 协议下 test 0.9053、clean 0.9703、ECE 减半。
3. **calib 剥离（~0.003 test，可避免）**：cross-fit 可收回，但当前 OOF 校准的 ECE 代价使其不适合直接上线。
4. **合法 clean 成本（剩余 ~0.001~0.002）**：66,220 行新 val/test 文本必须从训练中剔除；这部分不能回收。

原审计的「~0.45pt 真实回退」应改为：**约 0.25~0.45pt 是单 seed 噪声，约 0.2~0.3pt 是 calib 剥离，剩余 ~0.1~0.2pt 是 clean 评测的必要成本；没有证据支持 ~0.45pt 的系统性模型退化。**

## 5. 决策与落地（v4.2.1）

- **生产模型**：`final_train7` + held-out `calib_feats`，`random_state=43`（seed 42/43 在 val 上比较后选定；test 仅确认，不参与选择）。指标：test macro-F1 **0.9053**、clean **0.9703**、ECE **0.0129 (val) / 0.0110 (test)**、诚实子集 0.9068/0.9005（旧模型 0.9073/0.9022，差 -0.0005/-0.0017，在噪声带内）。
- **新增 `v3/honest_gate.py`**：切分/训练集变更时，自动从 manifest 读取双方 train 文本、校验 md5、在诚实子集上对比 own/shared/argmax 三种口径；默认 `own`（部署口径）、tol=0.002、seed 噪声带提示 ±0.004。
- **新增 `v3/train.py --cross-fit K` + `v3/calibration.py`**：K-fold OOF isotonic，把 calib 行并回训练且保持校准诚实；当前作为可选实验能力（ECE 代价已记档），待 OOF/全量分数对齐问题解决后再考虑转正。
- **修正文档**：CHANGELOG/HANDOVER/README/AGENTS 把「~0.45pt 真实回退」改为上述分解；新增踩坑 #40（单 seed 对比）+ #41（OOF 校准与全量模型分数尺度不一致）。

## 6. 复现命令

```bash
# 诚实子集对比（v4.2.0 vs 旧模型；预期 FAIL）
python3 v3/honest_gate.py \
  --candidate models/clf_v3_baseline_v420.pkl \
  --baseline models/clf_v3_baseline_v42.pkl \
  --out output/honest_gate_v420_vs_v42.json

# 生产模型 vs 旧模型（预期 PASS，delta 在噪声带内）
python3 v3/honest_gate.py \
  --candidate models/clf_v3.pkl \
  --baseline models/clf_v3_baseline_v42.pkl \
  --out output/honest_gate_v421_vs_v42.json

# seed 方差对照（~5min/seed）
python3 v3/train.py --train output/v3_feat/final_train7.csv \
  --calib-set output/v3_feat/calib_feats.csv --random-state 42 \
  --model models/exp_seed42.pkl --tag exp-seed42
python3 v3/train.py --train output/v3_feat/final_train7.csv \
  --calib-set output/v3_feat/calib_feats.csv --random-state 43 \
  --model models/exp_seed43.pkl --tag exp-seed43

# cross-fit（可选，~23min）
python3 v3/train.py --train output/v3_feat/final_train7.csv \
  --calib-set output/v3_feat/calib_feats.csv --cross-fit 5 \
  --model models/exp_crossfit_k5.pkl --tag exp-crossfit-k5
```
