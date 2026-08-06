"""tools/metrics.py 单元测试 — 共享度量函数 (v4.0.2 从 eval_classify 提取)"""
import io
import os
import sys
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.metrics import compute_metrics, print_metrics, LABELS


class TestMetrics(unittest.TestCase):
    def test_perfect_prediction(self):
        results = [(lb, lb) for lb in LABELS for _ in range(10)]
        m = compute_metrics(results)
        self.assertEqual(m["accuracy"], 1.0)
        self.assertEqual(m["macro_f1"], 1.0)
        self.assertEqual(m["total"], 40)
        for lb in LABELS:
            self.assertEqual(m["per_class"][lb]["f1"], 1.0)

    def test_all_wrong(self):
        results = [("ORG", "POI"), ("POI", "ADDR"),
                   ("ADDR", "UNKNOWN"), ("UNKNOWN", "ORG")]
        m = compute_metrics(results)
        self.assertEqual(m["accuracy"], 0.0)
        self.assertEqual(m["macro_f1"], 0.0)
        self.assertEqual(m["confusion_matrix"]["ORG"]["POI"], 1)

    def test_partial(self):
        results = [("ORG", "ORG"), ("ORG", "POI"),
                   ("POI", "POI"), ("POI", "POI")]
        m = compute_metrics(results)
        self.assertEqual(m["total"], 4)
        self.assertEqual(m["accuracy"], 0.75)
        org = m["per_class"]["ORG"]
        self.assertEqual(org["precision"], 1.0)
        self.assertEqual(org["recall"], 0.5)
        buf = io.StringIO()
        with redirect_stdout(buf):
            print_metrics(m, "t")
        self.assertIn("Macro-F1", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
