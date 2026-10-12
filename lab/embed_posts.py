"""lab_post 중 아직 벡터가 없거나 내용(해시)·모델이 바뀐 글을 임베딩 서비스로 계산해 lab_post_embedding에 넣는다.

실행: python -m lab.embed_posts   (임베딩 서비스가 떠 있어야 한다)
같은 글을 다시 실행하면 건너뛴다 (해시가 같으면 다시 계산하지 않는다).
"""

import json
import time
import urllib.request
from typing import List

from .config import EMBEDDER_URL, INTERNAL_SECRET
from .db import connect, vector_literal
from .textprep import build_embedding_text

BATCH = 4  # 긴 글이 섞여도 한 번에 너무 오래 걸리지 않게


def embed(texts: List[str]) -> dict:
    req = urllib.request.Request(
        EMBEDDER_URL + "/embed",
        data=json.dumps({"inputs": texts}).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-internal-secret": INTERNAL_SECRET},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as res:
        return json.loads(res.read())


def main() -> None:
    if not INTERNAL_SECRET:
        raise SystemExit(".env에 INTERNAL_SECRET이 없습니다.")
    health = json.loads(urllib.request.urlopen(EMBEDDER_URL + "/health", timeout=10).read())
    model = health["model"]

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.id, p.title, p.content_text, p.content_hash
            FROM lab_post p LEFT JOIN lab_post_embedding e ON e.post_id = p.id
            WHERE e.post_id IS NULL OR e.content_hash <> p.content_hash OR e.model <> %s
            ORDER BY p.published_at
            """,
            (model,),
        )
        todo = cur.fetchall()
        print(f"임베딩할 글: {len(todo)}개 (모델 {model})")

        started = time.perf_counter()
        for i in range(0, len(todo), BATCH):
            batch = todo[i : i + BATCH]
            body = embed([build_embedding_text(title, text) for _, title, text, _ in batch])
            for (post_id, _, _, digest), vector in zip(batch, body["embeddings"]):
                cur.execute(
                    """
                    INSERT INTO lab_post_embedding (post_id, model, content_hash, embedding)
                    VALUES (%s, %s, %s, %s::vector)
                    ON CONFLICT (post_id) DO UPDATE SET
                      model = EXCLUDED.model, content_hash = EXCLUDED.content_hash,
                      embedding = EXCLUDED.embedding, embedded_at = now()
                    """,
                    (post_id, body["model"], digest, vector_literal(vector)),
                )
            conn.commit()
            print(f"  {min(i + BATCH, len(todo))}/{len(todo)}  ({time.perf_counter() - started:.1f}s)")

        cur.execute("SELECT count(*) FROM lab_post_embedding")
        print(f"lab_post_embedding: {cur.fetchone()[0]}개")


if __name__ == "__main__":
    main()
