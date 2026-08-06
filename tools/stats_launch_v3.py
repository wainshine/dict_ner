import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.pipeline_base import launch_parallel

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ITER_DIR = os.path.join(BASE, "dicts", f"iter_{os.environ.get('DICT_VERSION', 'v1.5.0')}")

ok1 = launch_parallel(os.path.join(BASE, "tools", "org_chunk_stats_v3.py"),
                      os.path.join(BASE, "data", "split", "org"),
                      ITER_DIR,
                      "org_stats", label="org")
print("org stats:", ok1, flush=True)
ok2 = launch_parallel(os.path.join(BASE, "tools", "poi_chunk_stats_v3.py"),
                      os.path.join(BASE, "data", "split", "poi"),
                      ITER_DIR,
                      "poi_stats", label="poi")
print("poi stats:", ok2, flush=True)
