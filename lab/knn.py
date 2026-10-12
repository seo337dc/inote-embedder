"""가까운 이웃의 카테고리를 모아 카테고리를 제안하는 순수 함수들 — PLAN.md C단계의 핵심 아이디어를 DB 없이 검증한다."""

from typing import Dict, List, Sequence, Tuple

# (카테고리 이름, 유사도 점수) — 점수는 클수록 비슷하다
Neighbor = Tuple[str, float]


def vote_categories(neighbors: Sequence[Neighbor], k: int = 5, min_score: float = 0.0) -> List[Tuple[str, float]]:
    """가장 가까운 k개 이웃의 카테고리를 유사도 가중 투표해서 (카테고리, 가중치 합) 목록을 큰 순서로 돌려준다.

    - 점수가 min_score보다 낮은 이웃은 투표에서 뺀다 (억지로 제안하지 않기 위해)
    - 이웃이 하나도 없으면 빈 목록
    """
    weights: Dict[str, float] = {}
    for category, score in sorted(neighbors, key=lambda n: n[1], reverse=True)[:k]:
        if score < min_score:
            continue
        weights[category] = weights.get(category, 0.0) + score
    return sorted(weights.items(), key=lambda item: item[1], reverse=True)


def top_hit(actual: str, ranked: Sequence[Tuple[str, float]], n: int = 1) -> bool:
    """제안 상위 n개 안에 실제 카테고리가 있는가."""
    return actual in [name for name, _ in ranked[:n]]
