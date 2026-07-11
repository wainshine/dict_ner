import csv
import os
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional


class SegType(str, Enum):
    PROVINCE = "PROVINCE"
    CITY = "CITY"
    DISTRICT = "DISTRICT"
    TOWN = "TOWN"
    VILLAGE = "VILLAGE"
    COMMUNITY = "COMMUNITY"
    ROAD = "ROAD"
    POI = "POI"
    POI_SUB = "POI_SUB"
    ORG_SUFFIX = "ORG_SUFFIX"
    ORIENTATION = "ORIENTATION"
    NUMERIC = "NUMERIC"
    LOCATION = "LOCATION"
    INDUSTRY = "INDUSTRY"
    BRAND = "BRAND"  # used by OrgDPRecognizer to relabel UNKNOWN segments
    UNKNOWN = "UNKNOWN"
    CHAR = "CHAR"


LEVEL_ORDER = {
    SegType.PROVINCE: 0,
    SegType.CITY: 1,
    SegType.DISTRICT: 2,
    SegType.TOWN: 3,
    SegType.VILLAGE: 4,
    SegType.COMMUNITY: 4,
    SegType.ROAD: 5,
    SegType.POI: 6,
    SegType.ORG_SUFFIX: 6,
    SegType.POI_SUB: 7,
    SegType.ORIENTATION: -1,
    SegType.LOCATION: -1,
    SegType.INDUSTRY: -1,
    SegType.NUMERIC: -1,
    SegType.UNKNOWN: 99,
    SegType.CHAR: 100,
}


ADMIN_SUFFIX_MAP = {
    SegType.PROVINCE: {"省", "自治区", "特别行政区"},
    SegType.CITY: {"市", "自治州", "地区", "盟"},
    SegType.DISTRICT: {"区", "县", "旗", "自治县", "自治旗"},
    SegType.TOWN: {"镇", "乡", "街道", "民族乡", "苏木", "办事处"},
    SegType.VILLAGE: {"村", "庄", "屯", "寨"},
    SegType.COMMUNITY: {"社区", "居委会", "小区"},
    SegType.ROAD: {"路", "街", "道", "巷", "弄", "里", "大街", "大道",
                   "环路", "胡同", "条", "沿", "段", "线", "支路", "辅路", "匝道",
                   "山脚", "山口", "山根", "山前", "山后", "山下", "山腰",
                   "河沿", "河边", "河岸", "河畔", "河东", "河西",
                   "北街", "南街", "东街", "西街",
                   "东路", "西路", "南路", "北路", "中路",
                   "北道", "南道", "东道", "西道",
                   "县道", "乡道", "省道", "国道", "村道"},
}


LOCATION_SUFFIX_SET = {
    "院内", "场内", "楼内", "校内", "园内", "店内", "屋内", "室内", "局内",
    "旁", "旁边", "东旁", "西旁", "南旁", "北旁",
    "对面", "对过", "斜对面", "正对面",
    "东侧", "西侧", "南侧", "北侧",
    "以东", "以西", "以南", "以北",
    "向东", "向西", "向南", "向北",
    "西门", "东门", "南门", "北门", "正门", "后门", "侧门", "门口", "门前",
    "门上", "门下", "门旁", "门外", "门内",
    "底商", "底层", "一楼", "二楼", "三楼", "楼上", "楼下",
    "交汇处", "交叉口", "十字路口", "丁字路口", "三岔路口",
    "北行", "南行", "东行", "西行",
    "路东", "路西", "路南", "路北",
    "口东行", "口西行", "口南行", "口北行",
    "大门", "东大门", "西大门", "南大门", "北大门",
    "路边", "桥头", "桥下", "河对岸",
    "北段", "南段", "东段", "西段", "中段",
    "出口", "入口",
    # 地理特征（单字，作为方位词处理，不会破坏行政区划切分）
    # 注意：避免与ROAD后缀重叠的字
    "峰", "岭", "岗", "坡", "湾", "沟", "坝", "坪", "窑", "塘",
    "渠", "洞", "坑", "潭", "泉", "谷", "溪", "河", "湖",
    "海", "岛", "沙", "滩", "甸", "甸子", "草原", "箐", "畈",
    "崖", "壁", "林", "窝", "冲",
}


def _load_poi_suffix_map() -> Dict[str, str]:
    path = os.path.join(os.path.dirname(__file__), "..", "dicts", "poi_suffix_category.csv")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8-sig") as f:
        return {row["suffix"]: row["category"] for row in csv.DictReader(f)}


POI_SUFFIX_MAP = _load_poi_suffix_map()


@dataclass
class AddressSegment:
    text: str
    seg_type: SegType
    start: int
    end: int
    confidence: float = 1.0
    poi_type: Optional[str] = None

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass
class AddressResult:
    original: str
    segments: List[AddressSegment] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.segments) > 0

    def to_dict(self):
        return {
            "original": self.original,
            "segments": [
                {
                    "text": s.text,
                    "type": s.seg_type.value,
                    "poi_type": s.poi_type,
                    "confidence": round(s.confidence, 4),
                }
                for s in self.segments
            ],
        }
