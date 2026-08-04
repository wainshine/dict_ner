import os
from core.types import SegType

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DICT_DIR = os.path.join(BASE_DIR, "dicts")

VERSION = "v1.5.0"
NUM_CHUNKS = 16

ADDR_TYPES = {
    SegType.PROVINCE, SegType.CITY, SegType.DISTRICT,
    SegType.TOWN, SegType.VILLAGE, SegType.COMMUNITY, SegType.ROAD,
}
