"""
애플리케이션 진입점
Spring과 대응시키면 Application.java
"""

import math
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import MODEL_PATH
from app.predictor import get_predictor, is_loaded, load_predictor
from app.routers import prediction


def _sanitize(obj):
    # JSON으로 못 만드는 값(NaN, Infinity, 예외 객체)을 문자열로 바꿔 직렬화 가능하게 만든다
    if isinstance(obj, float) and not math.isfinite(obj):
        return str(obj)
    if isinstance(obj, BaseException):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


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
    # NaN, Infinity 입력은 에러 메시지에 원본값, 예외 객체가 그대로 담겨 JSON 직렬화가 깨진다 -> 정제 후 응답
    return JSONResponse(status_code=422, content={"detail": _sanitize(exc.errors())})


@app.get("/health", tags=["health"])
def health():
    if not is_loaded():
        # 503 = Service Unavailable
        # Gateway, Eureka가 상태코드로 판단한다
        return JSONResponse(status_code=503, content={"status": "DOWN"})

    return {"status": "UP", "modelVersion": get_predictor().version}
