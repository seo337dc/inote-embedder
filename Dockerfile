FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # 모델 파일은 이미지에 굽지 않고 첫 시작 때 이 폴더(볼륨)로 받는다 — 이미지를 다시 빌드해도 다시 받지 않는다
    HF_HOME=/models

WORKDIR /srv

# CPU 전용 torch를 먼저 설치한다. 기본 PyPI 휠은 CUDA 라이브러리가 딸려 와서 수 GB로 커진다.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

# root로 돌리지 않는다
RUN useradd --create-home app && mkdir -p /models && chown app /models
USER app

EXPOSE 8100

# 모델을 읽는 동안은 /health가 응답하지 않으므로 시작 유예 시간을 넉넉히 둔다
HEALTHCHECK --interval=15s --timeout=5s --start-period=180s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8100/health').status==200 else 1)"

# 워커는 1개 — 모델 객체를 한 번만 메모리에 올린다
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100", "--workers", "1"]
