"""
애플리케이션 진입점
Spring과 대응시키면 Application.java
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import MODEL_PATH
from app.errors import (
    COMMON_INTERNAL_SERVER_ERROR,
    COMMON_INVALID_REQUEST,
    error_body,
)
from app.predictor import get_predictor, is_loaded, load_predictor
from app.routers import prediction


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 기동 시 모델을 한 번만 로드한다 (Spring의 @PostConstruct 같은 것)
    load_predictor(MODEL_PATH)
    yield


app = FastAPI(
    title="Omagotchi Study-Time Prediction",
    description="learning-service가 보낸 피쳐로 내일 공부 시간을 예측한다",
    lifespan=lifespan,
)

app.include_router(prediction.router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # 예상 가능한 4xx: 스택트레이스는 남기지 않되, 필드별 원인은 진단용으로 로깅
    logger.warning(
        "validation failed: path = %s, errors = %s", request.url.path, exc.errors()
    )
    return JSONResponse(
        status_code=COMMON_INVALID_REQUEST.status,
        content=error_body(COMMON_INVALID_REQUEST, request.url.path),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # 예상치 못한 실패: 원본 예외는 로그에 보존하고, 응답에는 안전한 메시지만 노출
    logger.exception("unhandled exception: path = %s", request.url.path)
    return JSONResponse(
        status_code=COMMON_INTERNAL_SERVER_ERROR.status,
        content=error_body(COMMON_INTERNAL_SERVER_ERROR, request.url.path),
    )


@app.get("/health", tags=["health"])
def health():
    if not is_loaded():
        # 503 = Service Unavailable
        # Gateway, Eureka가 상태코드로 판단한다
        return JSONResponse(status_code=503, content={"status": "DOWN"})

    return {"status": "UP", "modelVersion": get_predictor().version}
