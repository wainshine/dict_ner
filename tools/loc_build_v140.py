import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
from v2.loc_builder import DictBuilder

b = DictBuilder("dicts", "loc_v1.4.0_base")
b.build_from_loc36kw("data")
b.build_from_areas("data")
b.build_from_d444("data")
b.cleanup()
b.build_orientation_dict()
b.build_location_dict()
b.save()
print("base saved", flush=True)
