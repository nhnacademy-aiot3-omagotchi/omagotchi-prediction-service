"""
애플리케이션 진입점
Spring과 대응시키면 Application.java
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import MODEL_PATH
from app.exception_handlers import register_exception_handlers
from app.predictor import get_predictor, load_predictor
from app.request_id import RequestIDMiddleware
from app.routers import prediction

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 기동 시 모델을 한 번만 로드한다 (Spring의 @PostConstruct 같은 것)
    # 필수 리소스이므로 실패하면 원본 예외를 그대로 전파해 기동 자체를 실패시킴 (의도적)
    load_predictor(MODEL_PATH)
    predictor = get_predictor()
    logger.info(
        "모델 로드 완료: version = %s, path = %s, features = %d",
        predictor.version,
        MODEL_PATH,
        predictor.feature_count,
    )

    yield


app = FastAPI(
    title="Omagotchi Study-Time Prediction",
    description="learning-service가 보낸 피쳐로 내일 공부 시간을 예측한다",
    lifespan=lifespan,
)

app.add_middleware(RequestIDMiddleware)
app.include_router(prediction.router)
register_exception_handlers(app)


@app.get("/health", tags=["health"])
def health():
    # 모델 로드 실패는 lifespan에서 기동 자체를 실패시키므로, 이 엔드포인트가 응답한다는 것은 모델이 로드됐다는 뜻임
    return {"status": "UP", "modelVersion": get_predictor().version}
