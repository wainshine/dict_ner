"""POI识别器 — 复用OrgDP, POI专用参数"""
import os
from org.recognizer import OrgDPRecognizer


class PoiRecognizer:
    def __init__(self, data_dir: str, dict_name: str = "poi_v1.1.1.pkl"):
        seed_path = os.path.join(os.path.dirname(data_dir), "data", "suffix_seed.csv")
        if not os.path.exists(seed_path):
            seed_path = os.path.join(data_dir, "suffix_seed.csv")
        self._rec = OrgDPRecognizer(
            data_dir, dict_name=dict_name,
            disable_short_d4_penalty=True,
            allow_adjacent_d4=True,
            poi_seed_path=seed_path if os.path.exists(seed_path) else None,
        )

    def recognize(self, text: str):
        return self._rec.recognize(text)
