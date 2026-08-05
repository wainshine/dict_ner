"""v3/engine/dp.py 单元测试 — 合成小词典, 不依赖大 pkl (快)"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.types import SegType, AddressSegment
from v3.engine.dp import DPEngine, EngineConfig, build_trie


def make_engine(entries=(), hooks=(), **kw):
    cfg = EngineConfig(
        name="test",
        entries=list(entries),
        trans_table=kw.pop("trans_table", {}),
        start_costs=kw.pop("start_costs", {}),
        word_cost_mode=kw.pop("word_cost_mode", "org"),
        single_char_cost=kw.pop("single_char_cost", 2.0),
        single_char_type=kw.pop("single_char_type", SegType.UNKNOWN),
        post_hooks=hooks,
        **kw,
    )
    return DPEngine(cfg)


def seg(text, stype, start=0, end=None):
    return AddressSegment(text=text, seg_type=stype, start=start,
                          end=end if end is not None else start + len(text))


class TestBuildTrie(unittest.TestCase):
    def test_collision_admin_priority_wins(self):
        # 同词碰撞: 行政优先级高者胜 (PROVINCE 0 < TOWN 3), 与 freq 无关
        trie, _, _ = build_trie([("某某", SegType.TOWN, 999999),
                                 ("某某", SegType.PROVINCE, 10)])
        node = trie["某"]["某"]
        self.assertEqual(node["#"][0], SegType.PROVINCE)

    def test_collision_same_level_higher_freq_wins(self):
        trie, _, _ = build_trie([("某某", SegType.TOWN, 10),
                                 ("某某", SegType.TOWN, 999)])
        self.assertEqual(trie["某"]["某"]["#"][1], 999)

    def test_type_counts(self):
        _, _, counts = build_trie([("甲", SegType.POI, 1),
                                   ("乙", SegType.POI, 1),
                                   ("丙", SegType.BRAND, 1)])
        self.assertEqual(counts[SegType.POI], 2)
        self.assertEqual(counts[SegType.BRAND], 1)


class TestWordCost(unittest.TestCase):
    def test_floor_05(self):
        e = make_engine(entries=[("高频词", SegType.POI, 10 ** 9)])
        cost = e._word_cost(SegType.POI, 10 ** 9, 3)
        self.assertGreaterEqual(cost, 0.5)

    def test_length_penalty_ordering(self):
        # 需要足够大的 type 总量使 IDF 为正, 否则全部触底 0.5
        entries = [(f"词{i:05d}", SegType.POI, 1000) for i in range(10000)]
        e = make_engine(entries=entries)
        c1 = e._word_cost(SegType.POI, 10, 1)
        c2 = e._word_cost(SegType.POI, 10, 2)
        c5 = e._word_cost(SegType.POI, 10, 5)
        self.assertGreater(c1, c2)   # 1字 +1.5
        self.assertGreater(c2, c5)   # 2字 +0.5, 3-8字 +0

    def test_freq0_org_mode(self):
        e = make_engine(word_cost_mode="org")
        self.assertEqual(e._word_cost(SegType.POI, 0, 2), 2.0)
        self.assertEqual(e._word_cost(SegType.POI, 0, 9), 4.0)

    def test_freq0_loc_mode(self):
        e = make_engine(word_cost_mode="loc")
        self.assertEqual(e._word_cost(SegType.LOCATION, 0, 2), 1.5)
        self.assertEqual(e._word_cost(SegType.POI, 0, 1), 4.0)


class TestRecognize(unittest.TestCase):
    def test_dict_word_beats_single_chars(self):
        e = make_engine(entries=[("华为", SegType.BRAND, 100000),
                                 ("有限公司", SegType.ORG_SUFFIX, 100000)])
        r = e.recognize("华为有限公司")
        types = [(s.text, s.seg_type) for s in r.segments]
        self.assertEqual(types, [("华为", SegType.BRAND),
                                 ("有限公司", SegType.ORG_SUFFIX)])

    def test_empty(self):
        e = make_engine()
        self.assertEqual(len(e.recognize("").segments), 0)
        self.assertEqual(len(e.recognize("   ").segments), 0)

    def test_short_d4_penalty(self):
        # 2字低频 POI 中部位: 无惩罚走词典, 有惩罚走单字兜底
        entries = [("咖啡", SegType.POI, 100)]
        flat = {}  # 所有转移代价默认 5.0 太贵, 压低以凸显词成本差异
        trans = {(a, b): 0.1 for a in (None, SegType.UNKNOWN, SegType.POI)
                 for b in (SegType.UNKNOWN, SegType.POI)}
        start = {SegType.UNKNOWN: 0.1, SegType.POI: 0.1}
        e_off = make_engine(entries=entries, trans_table=trans, start_costs=start,
                            short_d4_penalty=False)
        e_on = make_engine(entries=entries, trans_table=trans, start_costs=start,
                           short_d4_penalty=True)
        types_off = [s.seg_type for s in e_off.recognize("某某咖啡某某").segments]
        types_on = [s.seg_type for s in e_on.recognize("某某咖啡某某").segments]
        self.assertIn(SegType.POI, types_off)
        self.assertNotIn(SegType.POI, types_on)

    def test_post_hooks_applied(self):
        e = make_engine(hooks=("relabel_brand",))
        r = e.recognize("未登录词")
        self.assertTrue(all(s.seg_type == SegType.BRAND for s in r.segments))


class TestHooks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.e = make_engine()

    def test_merge_unknown(self):
        segs = [seg("未", SegType.UNKNOWN, 0), seg("知", SegType.UNKNOWN, 1),
                seg("店", SegType.POI, 2)]
        out = self.e._post_merge_unknown(segs)
        self.assertEqual([(s.text, s.seg_type) for s in out],
                         [("未知", SegType.UNKNOWN), ("店", SegType.POI)])
        self.assertEqual(out[0].end, 2)

    def test_trailing_single(self):
        segs = [seg("咖啡", SegType.INDUSTRY, 0), seg("档", SegType.UNKNOWN, 2)]
        out = self.e._post_trailing_single(segs)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].text, "咖啡档")
        self.assertEqual(out[0].seg_type, SegType.POI)

    def test_leading_bracket(self):
        segs = [seg("（", SegType.UNKNOWN, 0), seg("有限合伙）", SegType.POI, 1)]
        out = self.e._post_leading_bracket(segs)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].text, "（有限合伙）")
        self.assertEqual(out[0].start, 0)

    def test_relabel_brand(self):
        segs = [seg("某某", SegType.UNKNOWN, 0), seg("店", SegType.POI, 2)]
        out = self.e._post_relabel_brand(segs)
        self.assertEqual(out[0].seg_type, SegType.BRAND)
        self.assertEqual(out[1].seg_type, SegType.POI)

    def test_adjudicate_town_mid_position(self):
        # 中部位 bare TOWN + 后接 INDUSTRY → BRAND
        segs = [seg("深圳市", SegType.CITY, 0), seg("幸福", SegType.TOWN, 3),
                seg("餐饮", SegType.INDUSTRY, 5)]
        out = self.e._post_adjudicate_town(segs)
        self.assertEqual(out[1].seg_type, SegType.BRAND)

    def test_adjudicate_town_gov_protected(self):
        # 后接政府后缀 → 保持 TOWN
        segs = [seg("深圳市", SegType.CITY, 0), seg("幸福", SegType.TOWN, 3),
                seg("人民政府", SegType.POI, 5)]
        out = self.e._post_adjudicate_town(segs)
        self.assertEqual(out[1].seg_type, SegType.TOWN)

    def test_adjudicate_town_admin_suffix_skipped(self):
        # 带行政后缀的真镇名不动
        segs = [seg("深圳市", SegType.CITY, 0), seg("幸福镇", SegType.TOWN, 3),
                seg("餐饮", SegType.INDUSTRY, 6)]
        out = self.e._post_adjudicate_town(segs)
        self.assertEqual(out[1].seg_type, SegType.TOWN)

    def test_assign_poi_types(self):
        segs = [seg("人民医院", SegType.POI, 0), seg("华为", SegType.BRAND, 4)]
        out = self.e._post_assign_poi_types(segs)
        self.assertEqual(out[0].poi_type, "医院")
        self.assertIsNone(out[1].poi_type)

    def test_merge_same_type(self):
        segs = [seg("星光", SegType.POI, 0), seg("百货", SegType.POI, 2),
                seg("店", SegType.POI, 4)]
        out = self.e._post_merge_same_type(segs)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].text, "星光百货店")

    def test_strip_road_conjunction(self):
        segs = [seg("与香山路", SegType.ROAD, 0)]
        out = self.e._post_strip_road_conjunction(segs)
        self.assertEqual([(s.text, s.seg_type) for s in out],
                         [("与", SegType.UNKNOWN), ("香山路", SegType.ROAD)])


if __name__ == "__main__":
    unittest.main()
