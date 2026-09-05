"""FastAPI 애플리케이션 진입점."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.config import MODEL_PATH
from app.exception_handlers import register_exception_handlers
from app.observability import configure_observability
from app.predictor import get_predictor, load_predictor
from app.request_id import RequestIDMiddleware
from app.routers import prediction
from app.security import load_service_credential

configure_observability()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 필수 Credential 검증과 모델 적재 실패 시 기동 중단
    load_service_credential()
    load_predictor(MODEL_PATH)
    predictor = get_predictor()
    logger.info(
        "Prediction model loaded",
        extra={
            "event": {
                "dataset": "prediction-service.application",
                "action": "prediction.model.loaded",
                "outcome": "success",
            },
            "omagotchi": {
                "prediction": {
                    "model_version": predictor.version,
                    "feature_count": predictor.feature_count,
                }
            },
        },
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
FastAPIInstrumentor.instrument_app(
    app,
    excluded_urls=r".*/health$",
    exclude_spans=["receive", "send"],
)


@app.get("/health", tags=["health"])
def health():
    # 기동 과정의 모델 적재 성공을 전제로 한 준비 상태 응답
    return {"status": "UP", "modelVersion": get_predictor().version}
