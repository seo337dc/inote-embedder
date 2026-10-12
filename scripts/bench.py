"""임베딩 서비스 측정 스크립트 — 표준 라이브러리만 쓴다 (설치할 것 없음).

하는 일
  1) /health 로 모델 로드 확인
  2) 지연 측정: 짧은 문장 1개 / 짧은 문장 8개(배치) / 긴 글 1개(약 1,500자), 각각 여러 번 → 처음(콜드)과 중앙값
  3) 한국어 유사도 눈 확인: "비슷한 문장 쌍"이 "무관한 쌍"보다 확실히 높은지

사용
  INTERNAL_SECRET=... python scripts/bench.py [--url http://127.0.0.1:8100] [--repeat 5]
메모리는 다른 터미널에서  docker stats --no-stream  으로 따로 본다.
"""

import argparse
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request

SIMILAR_PAIRS = [
    ("오늘 점심으로 김치찌개를 먹었다", "점심 메뉴로 김치찌개를 먹었어요"),
    ("도커 컨테이너로 서버를 실행했다", "docker로 서버를 띄웠다"),
    ("리액트에서 상태를 관리하는 방법", "React 상태 관리 라이브러리 비교"),
    ("이직 준비를 위해 이력서를 고쳤다", "이력서를 수정하며 이직을 준비하고 있다"),
]
UNRELATED_PAIRS = [
    ("오늘 점심으로 김치찌개를 먹었다", "임베딩 모델은 문장을 벡터로 바꾼다"),
    ("도커 컨테이너로 서버를 실행했다", "주말에 가족과 제주도로 여행을 갔다"),
    ("리액트에서 상태를 관리하는 방법", "삼겹살은 불판에 바싹 구워야 맛있다"),
    ("이직 준비를 위해 이력서를 고쳤다", "비가 와서 우산을 챙겨 출근했다"),
]

SHORT = "도커로 임베딩 서비스를 띄워서 한국어 문장 벡터를 만들어 본다."
LONG = ("임베딩은 문장을 숫자 벡터로 바꾸는 방법이다. 뜻이 비슷한 문장은 벡터도 가까워진다. " * 24)[:1500]


def call(url: str, secret: str, inputs):
    req = urllib.request.Request(
        url + "/embed",
        data=json.dumps({"inputs": inputs}).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-internal-secret": secret},
        method="POST",
    )
    start = time.perf_counter()
    with urllib.request.urlopen(req, timeout=300) as res:
        body = json.loads(res.read())
    return (time.perf_counter() - start) * 1000, body


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def measure(url, secret, label, inputs, repeat):
    times = [call(url, secret, inputs)[0] for _ in range(repeat)]
    print(f"  {label:<28} 처음 {times[0]:8.0f} ms | 중앙값 {statistics.median(times):8.0f} ms | "
          f"최소 {min(times):8.0f} ms | 최대 {max(times):8.0f} ms")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8100")
    parser.add_argument("--repeat", type=int, default=5)
    args = parser.parse_args()
    secret = os.getenv("INTERNAL_SECRET", "")
    if not secret:
        print("INTERNAL_SECRET 환경 변수를 설정해 주세요.", file=sys.stderr)
        return 2

    try:
        with urllib.request.urlopen(args.url + "/health", timeout=10) as res:
            health = json.loads(res.read())
    except (urllib.error.URLError, OSError) as e:
        print(f"서비스에 연결하지 못했습니다: {e}", file=sys.stderr)
        return 1
    print(f"[health] {health}")
    if health.get("status") != "ok":
        print("모델을 아직 읽는 중입니다. 잠시 뒤 다시 실행해 주세요.", file=sys.stderr)
        return 1

    print(f"\n[지연] 각 {args.repeat}회 (한 번 데워진 뒤의 값은 '중앙값'을 본다)")
    measure(args.url, secret, "짧은 문장 1개", [SHORT], args.repeat)
    measure(args.url, secret, "짧은 문장 8개 (배치)", [SHORT] * 8, args.repeat)
    measure(args.url, secret, f"긴 글 1개 ({len(LONG)}자)", [LONG], args.repeat)

    print("\n[유사도] 비슷한 쌍은 높고, 무관한 쌍은 낮아야 한다 (정규화된 벡터의 내적 = 코사인 유사도)")
    sims, unrels = [], []
    for label, pairs, bucket in (("비슷함", SIMILAR_PAIRS, sims), ("무관함", UNRELATED_PAIRS, unrels)):
        for a, b in pairs:
            _, body = call(args.url, secret, [a, b])
            score = dot(*body["embeddings"])
            bucket.append(score)
            print(f"  {label}  {score:6.3f}  {a}  ↔  {b}")
    gap = statistics.mean(sims) - statistics.mean(unrels)
    print(f"\n  비슷한 쌍 평균 {statistics.mean(sims):.3f} / 무관한 쌍 평균 {statistics.mean(unrels):.3f} / 차이 {gap:.3f}")
    # 가장 낮은 '비슷함'이 가장 높은 '무관함'보다 높으면 이 작은 예에서는 깔끔하게 구분된다
    print(f"  가장 낮은 비슷함 {min(sims):.3f} > 가장 높은 무관함 {max(unrels):.3f} ? "
          f"{'예' if min(sims) > max(unrels) else '아니오 — 사례를 눈으로 확인할 것'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
