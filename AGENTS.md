# AGENTS.md — 新会话速通

> 给接手会话/agent 的 5 分钟上手文档。细节见 `README.md`（门面）与 `audit/HANDOVER.md`（架构/管线/血缘/决策/踩坑全录）。版本历史见 `CHANGELOG.md`。

## 项目一句话

中文地名/机构名/POI/品牌识别：统一 DP 引擎切分 + GBDT 分类器判 ORG/POI/ADDR/UNKNOWN，输出校准置信度。

## 当前状态

- 系统版本 **v4.0.1** | 词典 **v1.5.0**（loc/org/poi/brand 四词典统一编号） | 模型 `models/clf_v3.pkl`
- 指标：test macro-F1 0.9059 | clean accuracy 0.9919 | ECE 0.0129 | 单条 50ms / 批量 1.4ms/条
- 环境：macOS，Python 3.14，纯标准库 + sklearn/numpy/pandas（仅 v3/ 需要）+ fastapi/uvicorn（仅 serve.py）
- v4.0.0：v2 代码已迁 `/v2/`（平铺）+ 根 `pipeline_v2.py`；v3 不再 import 任何 v2 模块；HTTP 服务 `serve.py`

## 上手验证三连

```bash
cd /Users/wainshine/newAI/dict_ner
git status                                        # 应干净
python3 -m unittest discover -s tests/            # 181 条全绿
python3 run.py classify "深圳市南山区华为技术有限公司"   # → ORG (v3 默认入口)
python3 run.py v2 classify "广东省卫健委"           # → ORG (v2 冻结规则链)
```

## 文件地图

| 路径 | 说明 |
|------|------|
| `v3/` | **当前活代码**：engine/(统一DP引擎+gate门禁) features.py pipeline.py(自包含) brand_model.py infer.py fast_predict.py train.py labels.py 及全套评估/挖掘工具 |
| `v2/` + 根 `pipeline_v2.py` | **v2 冻结 baseline**：识别器平铺（loc_recognizer/loc_builder/loc_importer/org_recognizer/poi_recognizer/brand_model/eval）+ v2/tools/（v2 时代 launch/worker/eval 工具） |
| `core/` | 共享：types(SegType) / config(VERSION) / csv_index / suffix_matcher / suffix_classify |
| `serve.py` | FastAPI 服务：POST /classify /classify_batch、GET /health；压测见 output/v4_serve_bench.md |
| `models/` | clf_v3.pkl（GBDT+校准+乘数）+ manifest；clf_v3_compact.pkl（备选小模型） |
| `dicts/` | *v1.5.0.pkl 当前；v1.2.x=v2 baseline 保留；v1.1.x 兜底不可删；export/ 可读词频审计表；iter_v1.5.0/ stats 中间产物 |
| `data/` | 语料：split/{org,poi,loc,org_company}、SQL 三表、areas/、eval_split_*.csv、高德amap/腾讯地图（GBK 大文件） |
| `output/` | 评估产物；`v3_feat/` 特征中间体（`*_feats.csv` 主文件留，chunks/feats 分片可删可再生） |
| `tests/` | 181 条（tests/legacy/ 71 条 v2 锚定 + 根目录 110 条 v3/core/serve） |
| `audit/` | HANDOVER.md + 各代方案/审计报告 |

## 红线（违反即 reject）

1. `dicts/*v1.1.*.pkl` 兜底不可删；v1.2.x 是 v2 baseline 保留
2. v2 文件（`/v2/` + `pipeline_v2.py`）冻结只读
3. 词典任一变更 → 四词典版本号同升（统一版本政策）
4. 发版 = 代码 + README/HANDOVER/CHANGELOG 三文档 + git 提交，一次完成
5. 并行用 bash `&` 16 进程独立 .py（macOS spawn 坑）；跑性能测量前先杀干净后台 worker（OpenMP 过订阅）
6. `open(p,'w').write(open(p).read())` 会先截断后读取 → 清空文件，禁止此写法

## 常用命令

```bash
# 词典迭代（全链 ~1.5h）
STATS_VERSION=vX python3 tools/stats_launch_v3.py          # stats 重切
DICT_VERSION=vX python3 tools/org_aggregate.py             # aggregate
python3 tools/patch_v141.py --src-v vX --dst-v vY          # 补丁固化
# 分类器重训
python3 v3/precompute.py all <输入csv> <输出csv>            # 特征 (16进程)
python3 v3/labels.py --pool output/v3_feat/pool_feats.csv --flip 0.9
python3 v3/train.py --train <final_train> --calib-set output/v3_feat/train_feats.csv
# 门禁/评估
python3 v3/engine/gate.py --n 20000                        # 引擎一致性（现状下与 legacy v1.2.x 词典有代差 FAIL，验收看 diff 计数与变更前一致，见 HANDOVER §4.2）
python3 v3/seg_quality.py --engine org --n 200000 --v3     # 段健康度
python3 v3/evaluate.py --feats output/v3_feat/test_feats.csv  # test 指标
python3 v3/seg_compare.py run <org|poi|loc> <mode>         # 全量段对比
# 服务
uvicorn serve:app --port 8000 --workers 4                  # FastAPI 生产服务
```

## 下轮任务（v4.1.0 候选）

serve.py 压测已留档（单 worker 受 GIL 限制）；可选：pip 包化 pyproject.toml、多 worker 压测、Docker 化。
