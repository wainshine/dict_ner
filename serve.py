"""dict_ner FastAPI 服务 — v3 分类器对外 HTTP 接口

启动: uvicorn serve:app --host 0.0.0.0 --port 8000 --workers 2
"""
import json
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from core.config import SYSTEM_VERSION, VERSION as DICT_VERSION
from v3.infer import V3Classifier

_MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "models", "manifest_v3.json")


def _load_model_tag() -> str:
    try:
        with open(_MANIFEST_PATH, encoding="utf-8") as f:
            return json.load(f).get("tag", "unknown")
    except OSError:
        return "unknown"


class ClassifyRequest(BaseModel):
    text: str


class BatchRequest(BaseModel):
    texts: list[str]


_clf: V3Classifier | None = None
_started_at = time.time()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    global _clf, _started_at
    _clf = V3Classifier()
    _started_at = time.time()
    yield


app = FastAPI(title="dict_ner", version=SYSTEM_VERSION, lifespan=_lifespan)


@app.post("/classify")
def classify(req: ClassifyRequest):
    return _clf.classify(req.text)


@app.post("/classify_batch")
def classify_batch(req: BatchRequest):
    return _clf.classify_batch(req.texts)


@app.get("/health")
def health():
    return {
        "version": SYSTEM_VERSION,
        "dict_version": DICT_VERSION,
        "model_tag": _load_model_tag(),
        "uptime": round(time.time() - _started_at, 1),
    }
