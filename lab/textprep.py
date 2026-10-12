"""글(HTML)을 임베딩할 텍스트로 만드는 순수 함수들 — PLAN.md 5.4.

- HTML 태그를 지우고 공백을 정리한다 (script·style 안의 글자는 버린다).
- 임베딩 텍스트는 `제목 + 줄바꿈 + 본문 앞부분`. **카테고리는 넣지 않는다**(카테고리를 예측하는 실험에서 정답이 입력에 섞이면 안 된다).
- 해시가 같으면 다시 계산하지 않는다.
"""

import hashlib
import re
from html.parser import HTMLParser
from typing import List

# 본문 앞부분만 쓴다 — 길수록 느리다(글 한 편 약 1,150자에 2.6초). 측정해서 조정할 값.
DEFAULT_MAX_CHARS = 1500

_BLOCK_TAGS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "table"}
_SKIP_TAGS = {"script", "style"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    """HTML → 순수 텍스트. 줄바꿈은 문단 구분으로 남기고 나머지 공백은 하나로 줄인다."""
    parser = _TextExtractor()
    parser.feed(html or "")
    parser.close()
    text = "".join(parser.parts)
    lines = [re.sub(r"[ \t ]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def build_embedding_text(title: str, content_text: str, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """제목 + 줄바꿈 + 본문 앞부분(전체 max_chars자까지)."""
    return f"{title.strip()}\n{content_text.strip()}"[:max_chars].strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
