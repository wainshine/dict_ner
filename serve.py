"""dict_ner FastAPI 服务 — v3 分类器对外 HTTP 接口

启动: uvicorn serve:app --host 0.0.0.0 --port 8000 --workers 4
"""
import json
import logging
import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from core.config import SYSTEM_VERSION, VERSION as DICT_VERSION
from v3.infer import V3Classifier

logger = logging.getLogger(__name__)
MAX_TEXT = 1024
MAX_BATCH = 2048

_MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "models", "manifest_v3.json")


def _load_model_tag() -> str:
    try:
        with open(_MANIFEST_PATH, encoding="utf-8") as f:
            return json.load(f).get("tag", "unknown")
    except OSError:
        return "unknown"


class ClassifyRequest(BaseModel):
    text: str = Field(..., max_length=MAX_TEXT)


class BatchRequest(BaseModel):
    texts: list[str] = Field(..., max_length=MAX_BATCH)

    @field_validator("texts")
    @classmethod
    def _check_item_length(cls, texts):
        for text in texts:
            if len(text) > MAX_TEXT:
                raise ValueError(f"single text exceeds {MAX_TEXT} chars")
        return texts


_clf: V3Classifier | None = None
_clf_lock = threading.Lock()
_started_at = time.time()


def _require_clf() -> V3Classifier:
    if _clf is None:
        raise HTTPException(status_code=503, detail="classifier not ready")
    return _clf


@asynccontextmanager
async def _lifespan(app: FastAPI):
    global _clf, _started_at
    with _clf_lock:
        _clf = V3Classifier()
        _started_at = time.time()
        # 预热 CsvIndex 三个大表, 避免首波并发请求重复加载
        try:
            idx = _clf.extractor.idx
            idx.suffix
            idx.trade
            idx.addr
        except Exception as e:  # 预热失败不阻断启动, 端点仍按懒加载/降级运行
            logger.warning("CsvIndex prewarm failed: %s", e)
    yield


app = FastAPI(title="dict_ner", version=SYSTEM_VERSION, lifespan=_lifespan)


@app.post("/classify")
def classify(req: ClassifyRequest):
    return _require_clf().classify(req.text)


@app.post("/classify_batch")
def classify_batch(req: BatchRequest):
    return _require_clf().classify_batch(req.texts)


@app.get("/health")
def health():
    return {
        "version": SYSTEM_VERSION,
        "dict_version": DICT_VERSION,
        "model_tag": _load_model_tag(),
        "uptime": round(time.time() - _started_at, 1),
    }
