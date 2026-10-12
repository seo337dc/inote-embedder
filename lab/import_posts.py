"""배포된 BE의 공개 목록 API에서 **공개 글만** 가져와 lab_post에 넣는다 (여러 번 실행해도 안전: 같은 id는 덮어쓴다).

실행: python -m lab.import_posts
- 이 API는 비공개 글·임시저장을 내려주지 않는다. 그래도 한 번 더 확인해서, 비공개이거나 발행되지 않은 글이 섞여 오면 **버리고 알린다**.
"""

import json
import urllib.request
from typing import Dict, List

from .config import BLOG_API_URL
from .db import connect
from .textprep import build_embedding_text, content_hash, html_to_text

PAGE_SIZE = 50


def fetch_json(path: str) -> dict:
    req = urllib.request.Request(BLOG_API_URL + path, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as res:  # 무료 호스팅이 잠들어 있으면 첫 응답이 느리다
        return json.loads(res.read())


def fetch_all_public_posts() -> List[dict]:
    """고정 글(pinnedPage)과 일반 글(page)은 따로 페이지네이션된다 — 둘 다 끝까지 모은다."""
    posts: Dict[str, dict] = {}
    first = fetch_json(f"/blog/posts?pageSize={PAGE_SIZE}&page=1&pinnedPage=1")
    for p in first["pinned"] + first["items"]:
        posts[p["id"]] = p
    for page in range(2, int(first["totalPages"]) + 1):
        for p in fetch_json(f"/blog/posts?pageSize={PAGE_SIZE}&page={page}&pinnedPage=1")["items"]:
            posts[p["id"]] = p
    for pinned_page in range(2, int(first["pinnedTotalPages"]) + 1):
        for p in fetch_json(f"/blog/posts?pageSize={PAGE_SIZE}&page=1&pinnedPage={pinned_page}")["pinned"]:
            posts[p["id"]] = p
    return list(posts.values())


def main() -> None:
    posts = fetch_all_public_posts()
    print(f"가져온 글: {len(posts)}개 ({BLOG_API_URL})")

    skipped = [p for p in posts if p.get("isPrivate") or not p.get("publishedAt")]
    if skipped:
        print(f"⚠️ 비공개/미발행 글 {len(skipped)}개가 섞여 와서 버립니다: {[p['id'] for p in skipped]}")
    keep = [p for p in posts if p not in skipped]

    with connect() as conn, conn.cursor() as cur:
        for p in keep:
            text = html_to_text(p.get("content", ""))
            digest = content_hash(build_embedding_text(p["title"], text))
            cur.execute(
                """
                INSERT INTO lab_post (id, title, category, category_path, user_id, published_at, content_text, content_hash)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                  title = EXCLUDED.title, category = EXCLUDED.category, category_path = EXCLUDED.category_path,
                  user_id = EXCLUDED.user_id, published_at = EXCLUDED.published_at,
                  content_text = EXCLUDED.content_text, content_hash = EXCLUDED.content_hash
                """,
                (p["id"], p["title"], p.get("category", ""), p.get("categoryPath") or [], p.get("userId"),
                 p.get("publishedAt"), text, digest),
            )
        cur.execute("SELECT count(*), count(DISTINCT category), sum(length(content_text)) FROM lab_post")
        total, categories, chars = cur.fetchone()
    print(f"lab_post: {total}개, 카테고리 {categories}종, 본문 합계 {chars:,}자")


if __name__ == "__main__":
    main()
