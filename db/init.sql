-- 로컬 실험용 DB 초기화 (컨테이너가 처음 만들어질 때 한 번 실행된다).
-- 서비스(inote-server)의 PostEmbedding 설계(inote 레포 docs/kure/PLAN.md 5.3)를 실험용으로 단순화한 것 — 운영 스키마가 아니다.

CREATE EXTENSION IF NOT EXISTS vector;

-- 공개 API에서 가져온 공개 글만 들어온다 (비공개 글은 이 DB에 들어오지 않는다)
CREATE TABLE lab_post (
  id            text PRIMARY KEY,
  title         text NOT NULL,
  category      text NOT NULL,
  category_path text[] NOT NULL DEFAULT '{}',
  user_id       text,
  published_at  timestamptz,
  content_text  text NOT NULL,          -- HTML을 걷어낸 본문
  content_hash  text NOT NULL,          -- 임베딩할 텍스트(제목+본문 앞부분)의 해시
  imported_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE lab_post_embedding (
  post_id      text PRIMARY KEY REFERENCES lab_post(id) ON DELETE CASCADE,
  model        text NOT NULL,           -- 'nlpai-lab/KURE-v1'
  content_hash text NOT NULL,           -- 임베딩한 텍스트의 해시 — 같으면 다시 계산하지 않는다
  embedding    vector(1024) NOT NULL,
  embedded_at  timestamptz NOT NULL DEFAULT now()
);
-- 글이 수십 개라 인덱스 없이 전체 비교(정확)로 충분하다
