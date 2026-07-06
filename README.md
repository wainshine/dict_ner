# dict_ner v1.2.1

中文地名/机构名/POI/品牌识别系统。从非结构化中文文本中切分并标注段落类型。

## 快速开始

```bash
cd /Users/wainshine/newAI/dict_ner

# 交互识别
python run.py recognize "深圳市南山区华为技术有限公司"

# JSON 输出
python run.py json "北京市朝阳区星巴克咖啡国贸店"

# 内置测试集
python run.py test

# 版本信息
python run.py info
```

输出示例：

```
输入: 北京市朝阳区星巴克咖啡国贸店
  地名: [CITY]「北京市」 | [DISTRICT]「朝阳区」 | [POI]「星巴克咖啡国贸店」
  机构: [CITY]「北京市」 | [DISTRICT]「朝阳区」 | [POI]「星巴克」 | [INDUSTRY]「咖啡」 | [POI]「国贸店」
  POI:  [CITY]「北京市」 | [DISTRICT]「朝阳区」 | [POI]「星巴克」 | [POI]「咖啡」 | [POI]「国贸店」
```

## 四模组架构

```
输入文本
  │
  ├── loc/ (地名识别)     Viterbi DP + 120万行政词典
  ├── org/ (机构名识别)   四层: 地址+品牌+行业(INDUSTRY)+后缀
  ├── poi/ (POI识别)     复用机构DP + POI专用词典, 公司后缀自动排除
  └── brand/ (品牌模型)   字级bigram, 90万字符对, 分离度4.1

pipeline.py  统一总线
run.py       CLI入口
```

## 词典 (v1.1.1, 已收敛)

| 词典 | 条目 | 大小 | 说明 |
|------|------|:--:|------|
| `dicts/loc_v1.1.1.pkl` | 120万 | 25MB | 省/市/区/镇/村/路 10类 |
| `dicts/org_v1.1.1.pkl` | d1=66K d3=20K d4=9.6K | 1.8MB | d1≥5阈值 |
| `dicts/poi_v1.1.1.pkl` | d1=55K d3=4.8K d4=17K | 1.3MB | d1≥5 d3≥10 |
| `dicts/brand_v1.1.1.pkl` | 90万bigram | 10MB | 分离度4.1 |

## 目录结构

```
dict_ner/
├── core/         共享类型和常量 (SegType, Trie)
├── loc/          地名识别器 + 词典构建器
├── org/          机构名识别器
├── poi/          POI识别器 (thin wrapper over org DP)
├── brand/        品牌词概率模型
├── geomodel/     pickle 兼容层
├── pipeline.py   统一识别总线
├── run.py        CLI 入口
├── eval.py       评估脚本
├── tools/        训练/迭代工具
│   ├── org_launch.py / org_chunk_stats.py / org_aggregate.py
│   ├── poi_launch.py / poi_chunk_stats.py / poi_aggregate.py / poi_dedup.py
│   ├── org_sample_jsonl.py / org_eval.py
├── data/         语料与分片
│   ├── loc_corpus.csv (1.3GB)
│   ├── poi_deduped.txt (960MB, 去重后4000万条)
│   ├── addr/brand/trade/suffix_segments_sql.csv
│   ├── areas/ (五级行政区划)
│   ├── 公司名input.txt (1.2GB, 备用语料)
│   ├── 地名A/T input.txt (测试集)
│   └── split/{loc,org,poi}/ (16 chunk 分片)
├── dicts/        词典
│   ├── *v1.1.1.pkl (4个, 当前版)
│   ├── *v1.1.0.pkl (4个, 兜底旧版)
│   ├── suffix_seed.csv (POI后缀种子)
│   └── iter_v1.1.1/ (当前迭代数据)
└── output/
    └── org_sample_100k.jsonl (10万条机构识别样本)
```

## 识别质量

| 指标 | 值 |
|------|:--:|
| 地名 Score | 60.8 (5000条采样) |
| 机构 OK 率 | 93.3% (2万条采样) |
| 机构 d2_as_d4 | 3.6% |
| POI d4 覆盖 | 113% |
| POI d2 污染 | 0 (10类均已过滤) |
| 品牌分离度 | 4.1 log-units |

## 如何训练

### 地名

```bash
python -c "from loc.builder import DictBuilder; ..."
```

### 机构名 (16并行, ~6min)

```bash
python tools/org_launch.py clean stats
python tools/org_aggregate.py
```

### POI (16并行, ~4min)

```bash
python tools/poi_dedup.py              # 去重
python tools/poi_launch.py split stats
python tools/poi_aggregate.py
```

### 品牌模型 (~1min)

```python
from brand.model import BrandModel
model.train_from_d2_csv("dicts/iter_v1.1.1/org_d2_freqs_v1.1.1.csv", min_freq=3, min_bigram_count=10)
```

## 段类型说明

| 类型 | 含义 | 识别器 |
|------|------|--------|
| PROVINCE/CITY/DISTRICT/TOWN/VILLAGE/COMMUNITY/ROAD | 行政区划 | loc |
| LOCATION | 方位/位置描述 | loc |
| POI | 机构/POI后缀 | org/poi |
| INDUSTRY | 行业/业态类别 | org/poi |
| BRAND | 专名/品牌段 | org/poi |
| UNKNOWN | 未识别 | loc |
| ORIENTATION | 方向词 | loc |
| NUMERIC | 数字 | loc |

## 依赖

Python 3.10+, 纯标准库 (无第三方依赖)。

## 踩过的坑

1. **macOS spawn 模式**: Pool 子进程必须独立 .py 文件 + `if __name__ == '__main__'`, 最稳方案是 bash `&` 16进程后台
2. **d444 temp 字段**: 不是质量分, 是SQL处理阶段标记, 不要用来过滤
3. **体系循环**: loc/org/poi 三个系统的后缀词典各自演化, 互不混用
4. **d111 注入**: 只能fallback时用, POI用dict_name独立加载后必须跳过
5. **LOCATION 语义混用**: 地名用LOCATION(方位), 机构用INDUSTRY(行业), 通过SegType分离
6. **POI dict_name vs version**: POI训练时必须传dict_name而非version, 否则加载org词典
