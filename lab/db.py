import psycopg

from .config import db_url


def connect() -> "psycopg.Connection":
    return psycopg.connect(db_url())


def vector_literal(vector) -> str:
    """파이썬 숫자 목록 → pgvector 입력 문자열 '[0.1,0.2,...]' (%s::vector로 넘긴다)."""
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"
