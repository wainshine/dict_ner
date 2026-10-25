"""serve.py 单元测试 — FastAPI 契约 (TestClient)"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "models", "clf_v3.pkl")


@unittest.skipUnless(os.path.exists(MODEL_PATH), "v3 model not found")
class TestServe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from fastapi.testclient import TestClient
            import serve
        except ImportError:
            raise unittest.SkipTest("fastapi not available")
        cls.client_ctx = TestClient(serve.app)
        cls.client = cls.client_ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_ctx.__exit__(None, None, None)

    def test_health_fields(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        for k in ("version", "dict_version", "model_tag", "uptime"):
            self.assertIn(k, d)
        self.assertEqual(d["dict_version"], "v1.5.0")
        from core.config import SYSTEM_VERSION
        self.assertEqual(d["version"], SYSTEM_VERSION)

    def test_classify_contract(self):
        r = self.client.post("/classify",
                             json={"text": "深圳市南山区华为技术有限公司"})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["category"], "ORG")
        for k in ("text", "category", "confidence", "proba", "best", "all"):
            self.assertIn(k, d)
        self.assertAlmostEqual(sum(d["proba"].values()), 1.0, places=2)

    def test_classify_empty(self):
        d = self.client.post("/classify", json={"text": ""}).json()
        self.assertEqual(d["category"], "UNKNOWN")
        self.assertEqual(d["confidence"], 1.0)

    def test_classify_batch(self):
        r = self.client.post("/classify_batch", json={
            "texts": ["深圳市南山区华为技术有限公司", "北京市朝阳区", ""]})
        self.assertEqual(r.status_code, 200)
        out = r.json()
        self.assertEqual(len(out), 3)
        self.assertEqual(out[0]["category"], "ORG")
        self.assertEqual(out[1]["category"], "ADDR")
        self.assertEqual(out[2]["category"], "UNKNOWN")

    def test_classify_batch_matches_single(self):
        texts = ["海底捞火锅三里屯店", "广东省卫健委"]
        single = [self.client.post("/classify", json={"text": t}).json()
                  for t in texts]
        batch = self.client.post("/classify_batch",
                                 json={"texts": texts}).json()
        for s, b in zip(single, batch):
            self.assertEqual(s["category"], b["category"])

    def test_classify_bad_request(self):
        r = self.client.post("/classify", json={})
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()
