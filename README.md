# inote-embedder

한국어 임베딩 모델 **KURE-v1**(`nlpai-lab/KURE-v1`)로 텍스트를 벡터로 바꿔 주는 작은 HTTP 서비스와, 그걸 쓰는 **실험 모음**.
inote의 관련 글 추천·카테고리 제안·유사 글 알림·내 글 기반 답변(RAG)을 위한 기반이다.

> ⚠️ **임시 실험 레포.** 서비스(`inote`·`inote-server`·`inote-ai`)와 분리해서 먼저 검증하고, **합칠지·어디에 둘지는 결과를 보고 다시 정한다.**
> 설계 문서: `inote` 레포의 `docs/kure/PLAN.md` (A 기반 → B 관련 글 → C 제안·알림 → D RAG)

## 규칙
- **비공개 글·개인 데이터는 이 레포에 들어오지 않는다.** 실험 데이터는 공개 API에서 가져온 **공개 글만** 쓴다.
- `.env`와 `data/`는 git에 올리지 않는다. 비밀키는 이 로컬 실험용 값을 따로 만든다(운영 값 금지).
- 무거운 내려받기(도커 이미지, 파이썬 패키지, 모델)는 **크기를 알리고 허락받은 뒤** 한다.

## 구성
```
app/main.py              FastAPI 서비스 (POST /embed, GET /health)
lab/                     실험 스크립트 (로컬 DB 사용): textprep(HTML→텍스트) · knn(이웃 투표) · import_posts · embed_posts · neighbors
db/init.sql              로컬 pgvector DB 스키마 (lab_post, lab_post_embedding)
tests/                   API 테스트(가짜 인코더) + textprep·knn 테스트 — 모델·DB 없이 돈다
scripts/bench.py         지연·유사도 측정 (표준 라이브러리만)
Dockerfile               python:3.12-slim + CPU 전용 torch + sentence-transformers
docker-compose.yml       로컬 실행 (localhost:8100만 열림, 모델은 볼륨에 저장)
requirements.txt         서비스 의존성   requirements-test.txt  테스트 의존성   requirements-lab.txt  실험 스크립트(psycopg)
```

## API
```
POST /embed   헤더 x-internal-secret
  요청  { "inputs": ["문장1", "문장2"] }          # 1~16개, 각 최대 8,000자 (환경 변수로 조정)
  응답  { "model": "nlpai-lab/KURE-v1", "dim": 1024, "embeddings": [[...], [...]] }   # 정규화됨
GET  /health  → { "status": "ok" | "loading", "model": "...", "dim": 1024 }
```
- `INTERNAL_SECRET`이 설정돼 있지 않으면 `/embed`는 **503**으로 거절한다(열린 채로 뜨지 않게). 키가 없거나 틀리면 401.
- 모델 카드 확인(2026-10-12): BGE-M3 기반, 차원 **1024**, 최대 입력 **8192**, 라이선스 **MIT**, 접두어 언급 없음, 정규화 언급 없음 → 서비스가 직접 정규화한다.

## 실행
```bash
# 1) 테스트 (가상환경에 가벼운 의존성만 설치 — torch 불필요)
python3 -m venv .venv && .venv/bin/pip install -r requirements-test.txt
.venv/bin/python -m unittest discover -s tests -t . -v

# 2) 서비스 (첫 실행은 이미지 빌드 + 모델 내려받기로 오래 걸린다)
cp .env.example .env        # INTERNAL_SECRET을 채운다: openssl rand -hex 16
docker compose up --build

# 3) 측정 (서비스가 떠서 /health가 ok가 된 뒤)
INTERNAL_SECRET=... python3 scripts/bench.py
docker stats --no-stream     # 메모리
```
이 PC는 Intel Mac(CPU 추론), 도커 배정 자원은 CPU 12 · 메모리 약 7.75GB.

## 실험 실행 (A3) — 로컬 DB + 공개 글
```bash
# .env에 LAB_DB_PASSWORD도 채운다 (openssl rand -hex 16, 이 PC 안의 DB 전용)
.venv/bin/pip install -r requirements-lab.txt
docker compose up -d                       # embedder + db (db: localhost:5433)
.venv/bin/python -m lab.import_posts       # 배포된 BE의 공개 API에서 공개 글만 가져오기 (비공개 글은 안 들어옴)
.venv/bin/python -m lab.embed_posts        # 벡터 계산 (같은 글은 건너뜀)
.venv/bin/python -m lab.neighbors --all    # 모든 글의 가까운 글 3개
.venv/bin/python -m lab.neighbors --post "Docker"   # 특정 글의 가까운 글 5개
.venv/bin/python -m lab.neighbors --eval   # 이웃 투표로 카테고리 맞히기 (자기 자신 제외)
```
DB를 초기화하려면 `docker compose down -v`(모델 볼륨도 지워지니 주의: 필요하면 `docker volume rm inote-embedder_pgdata`만 지운다).

## 진행 상태
- [x] A1 Docker Desktop 설치·확인
- [x] A2 임베딩 서비스: 코드·테스트(12개) → 도커 빌드(이미지 약 427MB) → 모델 로드(첫 시작 약 2분) → 측정 — 결과는 `docs/a2-results.md`
- [x] A3 로컬 pgvector Postgres · 공개 글 가져오기 · 백필 · 가까운 이웃 확인 — 결과는 `docs/a3-results.md`
- [ ] A7 평가 세트 v0
