"""가까운 이웃을 눈으로 확인하고, 카테고리 제안(이웃 투표)이 얼마나 맞는지 본다.

실행
  python -m lab.neighbors --post "Docker"      # 제목에 포함된 글(또는 id)의 가까운 글 5개
  python -m lab.neighbors --all                # 모든 글의 가까운 글 3개 (한눈에 훑기)
  python -m lab.neighbors --eval               # 자기 자신을 뺀 이웃 투표로 카테고리 맞히기 (leave-one-out)
"""

import argparse
from collections import Counter
from typing import List, Tuple

from .db import connect
from .knn import top_hit, vote_categories

SQL_NEIGHBORS = """
SELECT p.id, p.title, p.category, 1 - (e.embedding <=> q.embedding) AS score
FROM lab_post_embedding e
JOIN lab_post p ON p.id = e.post_id,
     (SELECT embedding FROM lab_post_embedding WHERE post_id = %s) q
WHERE e.post_id <> %s
ORDER BY e.embedding <=> q.embedding
LIMIT %s
"""


def neighbors(cur, post_id: str, k: int) -> List[Tuple[str, str, str, float]]:
    cur.execute(SQL_NEIGHBORS, (post_id, post_id, k))
    return cur.fetchall()


def find_posts(cur, needle: str):
    cur.execute(
        "SELECT p.id, p.title, p.category FROM lab_post p JOIN lab_post_embedding e ON e.post_id = p.id "
        "WHERE p.id = %s OR p.title ILIKE %s ORDER BY p.published_at",
        (needle, f"%{needle}%"),
    )
    return cur.fetchall()


def show(cur, post, k: int) -> None:
    post_id, title, category = post
    print(f"\n■ [{category}] {title}")
    for _, n_title, n_cat, score in neighbors(cur, post_id, k):
        print(f"    {score:5.3f}  [{n_cat}] {n_title}")


def evaluate(cur) -> None:
    cur.execute("SELECT p.id, p.title, p.category FROM lab_post p JOIN lab_post_embedding e ON e.post_id = p.id")
    posts = cur.fetchall()
    categories = Counter(c for _, _, c in posts)
    print(f"평가 대상 {len(posts)}개 글, 카테고리 {len(categories)}종: {dict(categories)}")
    majority = categories.most_common(1)[0][1] / len(posts)
    print(f"기준선 — 항상 가장 많은 카테고리('{categories.most_common(1)[0][0]}')로 찍으면 {majority:.0%}")

    for k in (3, 5):
        hit1 = hit3 = 0
        wrong = []
        for post_id, title, actual in posts:
            ranked = vote_categories([(c, s) for _, _, c, s in neighbors(cur, post_id, k)], k=k)
            hit1 += top_hit(actual, ranked, 1)
            hit3 += top_hit(actual, ranked, 3)
            if not top_hit(actual, ranked, 1):
                wrong.append((title, actual, ranked[:2]))
        print(f"\n[k={k}] 1순위 적중 {hit1}/{len(posts)} ({hit1 / len(posts):.0%}) · 상위 3개 안 적중 {hit3}/{len(posts)} ({hit3 / len(posts):.0%})")
        if k == 5:
            for title, actual, ranked in wrong:
                print(f"    ✗ {title}  실제 '{actual}' ← 제안 {[(n, round(w, 2)) for n, w in ranked]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--post")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--eval", action="store_true")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    with connect() as conn, conn.cursor() as cur:
        if args.eval:
            evaluate(cur)
        elif args.all:
            cur.execute("SELECT p.id, p.title, p.category FROM lab_post p JOIN lab_post_embedding e ON e.post_id = p.id ORDER BY p.published_at")
            for post in cur.fetchall():
                show(cur, post, 3)
        elif args.post:
            found = find_posts(cur, args.post)
            if not found:
                raise SystemExit("찾는 글이 없습니다.")
            for post in found[:3]:
                show(cur, post, args.k)
            if len(found) > 3:
                print(f"\n(그 밖에 {len(found) - 3}개 더 — 더 구체적으로 검색해 보세요)")
        else:
            parser.print_help()


if __name__ == "__main__":
    main()
