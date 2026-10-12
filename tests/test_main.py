"""임베딩 서비스 API 테스트 — 모델(torch) 없이 가짜 인코더로 돌린다.

실행: python -m unittest discover -s tests -t . -v   (레포 루트에서, fastapi·httpx가 설치된 파이썬으로)
"""

import math
import unittest
from typing import List

from fastapi.testclient import TestClient

from app.main import Encoder, Settings, create_app

SECRET = "test-secret"
HEADERS = {"x-internal-secret": SECRET}


class FakeEncoder(Encoder):
    """글자 수와 첫 글자로 만든 4차원 정규화 벡터 — 계산 호출을 기록한다."""

    model_name = "fake/model"
    dim = 4

    def __init__(self):
        self.calls: List[List[str]] = []

    def encode(self, texts: List[str]) -> List[List[float]]:
        self.calls.append(list(texts))
        out = []
        for t in texts:
            v = [float(len(t)), float(ord(t[0]) % 7), 1.0, 2.0]
            norm = math.sqrt(sum(x * x for x in v))
            out.append([x / norm for x in v])
        return out


class EmbedApiTest(unittest.TestCase):
    def make_client(self, **settings):
        self.encoder = FakeEncoder()
        cfg = Settings(secret=settings.pop("secret", SECRET), **settings)
        return TestClient(create_app(encoder=self.encoder, settings=cfg))

    # --- /health ---
    def test_health는_인증_없이도_모델과_차원을_알려준다(self):
        with self.make_client() as client:
            res = client.get("/health")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")
        self.assertEqual(res.json()["dim"], 4)

    # --- 인증 ---
    def test_비밀키가_없으면_401(self):
        with self.make_client() as client:
            res = client.post("/embed", json={"inputs": ["안녕"]})

        self.assertEqual(res.status_code, 401)
        self.assertEqual(self.encoder.calls, [])  # 인증 전에는 모델을 쓰지 않는다

    def test_비밀키가_틀리면_401(self):
        with self.make_client() as client:
            res = client.post("/embed", json={"inputs": ["안녕"]}, headers={"x-internal-secret": "wrong"})

        self.assertEqual(res.status_code, 401)

    def test_서비스에_비밀키가_설정돼_있지_않으면_모든_요청을_거절한다(self):
        with self.make_client(secret="") as client:
            res = client.post("/embed", json={"inputs": ["안녕"]}, headers=HEADERS)
            empty_header = client.post("/embed", json={"inputs": ["안녕"]}, headers={"x-internal-secret": ""})

        self.assertEqual(res.status_code, 503)
        self.assertEqual(empty_header.status_code, 503)

    # --- 정상 응답 ---
    def test_문장마다_같은_순서로_벡터를_돌려준다(self):
        with self.make_client() as client:
            res = client.post("/embed", json={"inputs": ["짧은", "조금 더 긴 문장입니다"]}, headers=HEADERS)

        body = res.json()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(body["model"], "fake/model")
        self.assertEqual(body["dim"], 4)
        self.assertEqual(len(body["embeddings"]), 2)
        self.assertEqual(body["embeddings"], self.encoder.encode(["짧은", "조금 더 긴 문장입니다"]))

    def test_여러_문장은_한_번의_계산으로_처리한다(self):
        with self.make_client() as client:
            client.post("/embed", json={"inputs": ["하나", "둘", "셋"]}, headers=HEADERS)

        self.assertEqual(len(self.encoder.calls), 1)
        self.assertEqual(self.encoder.calls[0], ["하나", "둘", "셋"])

    # --- 입력 검증 ---
    def test_빈_목록은_422(self):
        with self.make_client() as client:
            res = client.post("/embed", json={"inputs": []}, headers=HEADERS)

        self.assertEqual(res.status_code, 422)

    def test_한_번에_받는_개수를_넘으면_422(self):
        with self.make_client(max_batch=2) as client:
            ok = client.post("/embed", json={"inputs": ["a", "b"]}, headers=HEADERS)
            too_many = client.post("/embed", json={"inputs": ["a", "b", "c"]}, headers=HEADERS)

        self.assertEqual(ok.status_code, 200)
        self.assertEqual(too_many.status_code, 422)

    def test_빈_문장이나_공백만_있는_문장은_422(self):
        with self.make_client() as client:
            empty = client.post("/embed", json={"inputs": ["정상", ""]}, headers=HEADERS)
            blank = client.post("/embed", json={"inputs": ["   \n"]}, headers=HEADERS)

        self.assertEqual(empty.status_code, 422)
        self.assertEqual(blank.status_code, 422)
        self.assertEqual(self.encoder.calls, [])  # 검증에서 걸리면 계산하지 않는다

    def test_문장_하나가_최대_글자수를_넘으면_422(self):
        with self.make_client(max_chars=5) as client:
            ok = client.post("/embed", json={"inputs": ["12345"]}, headers=HEADERS)
            too_long = client.post("/embed", json={"inputs": ["123456"]}, headers=HEADERS)

        self.assertEqual(ok.status_code, 200)
        self.assertEqual(too_long.status_code, 422)

    def test_inputs가_문자열_목록이_아니면_422(self):
        with self.make_client() as client:
            not_list = client.post("/embed", json={"inputs": "문장"}, headers=HEADERS)
            not_str = client.post("/embed", json={"inputs": [1, 2]}, headers=HEADERS)
            missing = client.post("/embed", json={}, headers=HEADERS)

        self.assertEqual(not_list.status_code, 422)
        self.assertEqual(not_str.status_code, 422)
        self.assertEqual(missing.status_code, 422)


class SettingsTest(unittest.TestCase):
    def test_환경_변수에서_설정을_읽고_없으면_기본값을_쓴다(self):
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = Settings.from_env()
        self.assertEqual(cfg.model_name, "nlpai-lab/KURE-v1")
        self.assertEqual(cfg.max_batch, 16)
        self.assertEqual(cfg.secret, "")

        env = {"EMBEDDER_MODEL": "x/y", "EMBEDDER_MAX_BATCH": "4", "EMBEDDER_MAX_CHARS": "100", "INTERNAL_SECRET": "s"}
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = Settings.from_env()
        self.assertEqual((cfg.model_name, cfg.max_batch, cfg.max_chars, cfg.secret), ("x/y", 4, 100, "s"))


if __name__ == "__main__":
    unittest.main()
