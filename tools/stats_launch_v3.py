import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import VERSION as CURRENT_DICT_VERSION
from tools.pipeline_base import launch_parallel

if not os.environ.get("STATS_VERSION"):
    print("STATS_VERSION is required, e.g. STATS_VERSION=v1.4.3", file=sys.stderr)
    sys.exit(2)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DICT_VERSION = os.environ.get("DICT_VERSION", CURRENT_DICT_VERSION)
ITER_DIR = os.path.join(BASE, "dicts", f"iter_{DICT_VERSION}")
print(f"STATS_VERSION={os.environ['STATS_VERSION']} DICT_VERSION={DICT_VERSION} "
      f"-> {ITER_DIR}", flush=True)

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
