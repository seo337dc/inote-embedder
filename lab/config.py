"""실험 스크립트 공통 설정 — .env와 환경 변수에서 읽는다 (외부 패키지 없이)."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env(path: Path = ROOT / ".env") -> None:
    """KEY=VALUE 줄을 환경 변수로 넣는다. 이미 있는 환경 변수는 덮어쓰지 않는다."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()

# 임베딩 서비스 (docker compose의 embedder)
EMBEDDER_URL = os.getenv("EMBEDDER_URL", "http://127.0.0.1:8100")
INTERNAL_SECRET = os.getenv("INTERNAL_SECRET", "")

# 공개 글을 가져올 곳 — 배포된 BE의 **공개** 목록 API(로그인 없이 누구나 읽는 글). 비공개 글은 이 API로 나오지 않는다.
BLOG_API_URL = os.getenv("BLOG_API_URL", "https://inote-server-5a63.onrender.com/api/v1")


def db_url() -> str:
    password = os.getenv("LAB_DB_PASSWORD")
    if not password:
        raise SystemExit(".env에 LAB_DB_PASSWORD가 없습니다 (README 참고).")
    return f"postgresql://lab:{password}@127.0.0.1:{os.getenv('LAB_DB_PORT', '5433')}/lab"
