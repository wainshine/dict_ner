# v4.2.2 自审计 — seed43 是 winner's curse，v4.2.1 的修正被推翻

> 触发：v4.2.1 发布后自审计，补跑 seed44/45，检验「seed43 全指标更好」是否只是又一次单点运气。
> 样本：`final_train7` + held-out `calib_feats`，只改 `random_state`（42/43/44/45），其余协议完全一致。
> **结论：v4.2.1 的「原审计 ~0.45pt 回退不成立」是错的。** seed42 接近 4-seed 均值，seed43 是 4 个 seed 的最高值；v4.2.1 从 2 个 seed 里挑 seed43，再用 test「确认」，是典型 winner's curse。原审计的诚实子集 -0.0047/-0.0043 与 4-seed 均值 -0.0033/-0.0039 同向同量级，**真实回退成立**。

## 1. 4-seed 分布（同一 final_train7 + held-out calib）

| seed | val macro-F1 | test macro-F1 | clean | ECE val / test | 诚实 val / test（各自乘数） |
|---:|---:|---:|---:|---:|---:|
| 42（v4.2.0） | 0.9053 | 0.9035 | 0.9689 | 0.0253 / 0.0215 | 0.9026 / 0.8979 |
| 43（v4.2.1） | **0.9082** | **0.9053** | **0.9703** | **0.0129 / 0.0110** | **0.9068 / 0.9005** |
| 44 | 0.9053 | 0.9042 | 0.9690 | 0.0110 / 0.0078 | 0.9044 / 0.8972 |
| 45 | 0.9052 | 0.9032 | 0.9674 | 0.0300 / 0.0266 | 0.9021 / 0.8975 |
| **mean** | **0.9060** | **0.9041** | **0.9689** | **0.0198 / 0.0167** | **0.9040 / 0.8983** |
| std (ddof=1) | 0.0015 | 0.0009 | 0.0012 | 0.0093 / 0.0088 | 0.0021 / 0.0015 |

诚实子集（旧模型 `final_train6` 未见文本）：val 13,991 / test 14,019；旧模型 0.9073 / 0.9022。

- 4-seed 均值 vs 旧模型：**-0.0033 (val) / -0.0039 (test)**。
- seed42 vs 旧模型：-0.0047 / -0.0043（接近均值，**不是 unlucky outlier**）。
- seed43 vs 旧模型：-0.0005 / -0.0017（**4 个 seed 里最好的一个**）。

原审计报告的 -0.0047/-0.0043 不是「偏差抽样」，而是接近分布中心；v4.2.1 用 seed43 的 -0.0005/-0.0017 宣称「回退不成立」，是把最大值当成了典型值。

## 2. 其他被推翻的 v4.2.1 表述

| v4.2.1 表述 | 4-seed 事实 |
|---|---|
| 「seed42 是偏差抽样」 | seed42 的 test/诚实子集接近均值；seed43 才是 +1.5~2σ 的高值 |
| 「test 0.9035→0.9053 是确认」 | test 4-seed 范围 0.9032~0.9053，均值 0.9041；0.9053 是最大值，选取后不可当无偏估计 |
| 「clean 0.9689→0.9703」 | 4-seed 均值 0.9689，与 v4.2.0 完全相同；+0.0014 是 seed43 单点 |
| 「ECE 0.0253/0.0215→0.0129/0.0110，约减半」 | ECE 4-seed 范围 0.0078~0.0300，std 0.009；seed43/44 好、seed42/45 差，是双峰 seed 运气，不是稳定收益 |

## 3. 真实回退与 cross-fit

- 真实回退：诚实子集 **~0.35~0.4pt**（4-seed 均值 -0.0033/-0.0039），不是 ~0.45pt 但同量级；原审计方向与量级基本正确。
- cross-fit（seed42，calib 并回训练 + OOF isotonic）：test **0.9069**、clean **0.9738**、诚实 **0.9069/0.9013**（vs 旧模型 -0.0004/-0.0009，vs 4-seed 均值 +0.0028/+0.0030），确实收回了大部分回退。
- 但 cross-fit 的 OOF 校准 ECE **0.0325/0.0332**，即使加 val temperature 也只到 0.0258/0.0251；作为可选能力保留，待 OOF/全量分数尺度对齐后再考虑转正。
- **下一步正路**：修 cross-fit 校准（quantile alignment / K=10 / fold ensemble），目标是同时拿到 honest +0.003 与 ECE ≤0.02。

## 4. 修正（v4.2.2）

- **生产模型回退 seed42**（固定 seed，不按 val 挑 seed）：test **0.9035**、clean **0.9689**、ECE **0.0253/0.0215**；这是 v4.2.0 模型，4-seed 均值 0.9041/0.9689/0.0198/0.0167 作为上下文披露。
- **诚实门禁**: seed42 vs 旧模型 **FAIL**（own -0.0047 val / -0.0043 test，tol 0.002）；这是真实回退，v4.2.2 不掩盖。cross-fit (seed42) vs 旧 -0.0004/-0.0009（PASS），但 OOF 校准 ECE 0.0325，暂不转正。
- **seed 协议**：固定 seed（42）或 ≥3 seeds 均值/区间；**禁止从多个 seed 中挑 val 最高的一个**再用 test 确认；`honest_gate` 只用于固定 seed 候选，不用于 seed 选择。
- **v4.2.1 文档作废声明**：CHANGELOG v4.2.1 加警告；`audit_v421_honest_subset.md` 顶部加 superseded 标记；README/AGENTS/HANDOVER 指标回退 seed42。
- **保留**：`v3/honest_gate.py`、`v3/train.py --cross-fit K`、`--random-state`、confidence temperature、HANDOVER #40/#41；#40 改写为「单 seed 对比 + 挑 seed」双重教训。

## 5. 复现

```bash
for s in 42 43 44 45; do
  python3 v3/train.py --train output/v3_feat/final_train7.csv \
    --calib-set output/v3_feat/calib_feats.csv --random-state $s \
    --model models/exp_seed$s.pkl --tag exp-seed$s
done

# 逐模型跑 evaluate/clean_eval/calibration_audit（或 audit 脚本），汇总 mean/std。
# 诚实子集对比（固定 seed42 生产模型）：
python3 v3/honest_gate.py --candidate models/clf_v3.pkl \
  --baseline models/clf_v3_baseline_v42.pkl
```
