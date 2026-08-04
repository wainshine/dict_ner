import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.pipeline_base import launch_parallel

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ok1 = launch_parallel(os.path.join(BASE, "tools", "org_chunk_stats_v3.py"),
                      os.path.join(BASE, "data", "split", "org"),
                      os.path.join(BASE, "dicts", "iter_v1.5.0"),
                      "org_stats", label="org")
print("org stats:", ok1, flush=True)
ok2 = launch_parallel(os.path.join(BASE, "tools", "poi_chunk_stats_v3.py"),
                      os.path.join(BASE, "data", "split", "poi"),
                      os.path.join(BASE, "dicts", "iter_v1.5.0"),
                      "poi_stats", label="poi")
print("poi stats:", ok2, flush=True)
