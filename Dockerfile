FROM python:3.12-slim

# curl: Compose healthcheck용
# libgomp1: LightGBM이 요구하는 OpenMP 런타임 (slim 이미지에 없어 누락 시 모델 로드 실패)
RUN apt-get update && apt-get install -y --no-install-recommends curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY models/ models/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]