"""임베딩 서비스 — 텍스트를 KURE-v1 벡터로 바꿔 주는 작은 HTTP 서비스.

계약 (자세한 설계: inote 레포 docs/kure/PLAN.md 5.2)
  POST /embed   헤더 x-internal-secret   { "inputs": ["문장1", ...] }
                → { "model": "...", "dim": 1024, "embeddings": [[...], ...] }   (정규화된 벡터)
  GET  /health  → { "status": "ok", "model": "...", "dim": 1024 }

설계 메모
- 모델(torch)은 무거워서 이 파일을 불러올 때가 아니라 **서비스가 시작될 때** 읽는다. 테스트는 가짜 인코더를 넣어서(create_app)
  모델 없이 돌린다.
- 비밀키(INTERNAL_SECRET)가 설정돼 있지 않으면 **모든 /embed 요청을 거절**한다(열어 둔 채로 뜨지 않게).
- 파이썬 3.9에서도 돌도록 `X | None` 대신 Optional을 쓴다 (이 PC의 기본 파이썬이 3.9).
"""

import os
import secrets
import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel


@dataclass(frozen=True)
class Settings:
    model_name: str = "nlpai-lab/KURE-v1"
    # 한 번에 받는 글 수와 글 하나의 최대 글자 수 — 느려지거나 메모리가 부족해지지 않게 상한을 둔다
    max_batch: int = 16
    max_chars: int = 8000
    secret: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            model_name=os.getenv("EMBEDDER_MODEL", cls.model_name),
            max_batch=int(os.getenv("EMBEDDER_MAX_BATCH", str(cls.max_batch))),
            max_chars=int(os.getenv("EMBEDDER_MAX_CHARS", str(cls.max_chars))),
            secret=os.getenv("INTERNAL_SECRET", ""),
        )


class Encoder:
    """텍스트 목록 → 정규화된 벡터 목록. 테스트에서는 이 모양의 가짜를 넣는다."""

    model_name: str
    dim: int

    def encode(self, texts: List[str]) -> List[List[float]]:  # pragma: no cover - 인터페이스
        raise NotImplementedError


class SentenceTransformerEncoder(Encoder):
    def __init__(self, model_name: str):
        # 무거운 import는 여기서 — 이 클래스를 만들 때(=서비스 시작 때)만 읽는다
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self._model = SentenceTransformer(model_name)
        # sentence-transformers 6.x에서 이름이 get_embedding_dimension으로 바뀌었다 (옛 이름은 경고) — 둘 다 받는다
        get_dim = getattr(self._model, "get_embedding_dimension", None) or self._model.get_sentence_embedding_dimension
        self.dim = int(get_dim())
        # 같은 모델 객체에 동시에 여러 요청이 들어와도 CPU를 두고 다투지 않게 한 번에 하나씩 계산한다
        self._lock = threading.Lock()

    def encode(self, texts: List[str]) -> List[List[float]]:
        with self._lock:
            # 모델 카드에 정규화 여부가 안 적혀 있어서 직접 정규화한다 (코사인 유사도 = 내적이 되도록)
            vectors = self._model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return vectors.tolist()


class EmbedRequest(BaseModel):
    inputs: List[str]


class EmbedResponse(BaseModel):
    model: str
    dim: int
    embeddings: List[List[float]]


def create_app(encoder: Optional[Encoder] = None, settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 테스트가 가짜 인코더를 넣었으면 그걸 쓰고, 아니면 모델을 읽는다(시간이 걸린다)
        app.state.encoder = encoder or SentenceTransformerEncoder(settings.model_name)
        yield

    app = FastAPI(title="inote-embedder", lifespan=lifespan)

    def require_secret(x_internal_secret: Optional[str] = Header(default=None)) -> None:
        if not settings.secret:
            # 비밀키 없이 열린 서비스가 되지 않도록 거절한다
            raise HTTPException(status_code=503, detail="INTERNAL_SECRET이 설정되지 않았습니다.")
        # 시간 차이로 비밀키를 추측하지 못하게 상수 시간 비교
        if not x_internal_secret or not secrets.compare_digest(x_internal_secret, settings.secret):
            raise HTTPException(status_code=401, detail="인증에 실패했습니다.")

    @app.get("/health")
    def health():
        loaded = getattr(app.state, "encoder", None)
        return {
            "status": "ok" if loaded else "loading",
            "model": settings.model_name,
            "dim": loaded.dim if loaded else None,
        }

    # def(동기) 함수로 둬서 계산이 이벤트 루프를 막지 않고 스레드풀에서 돈다
    @app.post("/embed", response_model=EmbedResponse, dependencies=[Depends(require_secret)])
    def embed(body: EmbedRequest):
        inputs = body.inputs
        if not inputs or len(inputs) > settings.max_batch:
            raise HTTPException(status_code=422, detail=f"inputs는 1~{settings.max_batch}개여야 합니다.")
        for text in inputs:
            if not text.strip():
                raise HTTPException(status_code=422, detail="빈 문장은 임베딩할 수 없습니다.")
            if len(text) > settings.max_chars:
                raise HTTPException(status_code=422, detail=f"문장 하나는 {settings.max_chars}자까지입니다.")

        enc: Encoder = app.state.encoder
        return EmbedResponse(model=enc.model_name, dim=enc.dim, embeddings=enc.encode(inputs))

    return app


# uvicorn app.main:app 이 읽는 앱 — 시작할 때 모델을 읽는다
app = create_app()
