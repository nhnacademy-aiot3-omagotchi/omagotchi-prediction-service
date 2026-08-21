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
from app.request_id import REQUEST_ID_HEADER, RequestIDMiddleware, get_request_id
from app.routers import prediction

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 기동 시 모델을 한 번만 로드한다 (Spring의 @PostConstruct 같은 것)
    # 실패해도 앱은 반드시 기동해야 /health가 503을 보고할 수 있음
    try:
        load_predictor(MODEL_PATH)
    except Exception:
        logger.exception(
            "모델 로드 실패 - DOWN 상태로 기동합니다: path = %s", MODEL_PATH
        )
    else:
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


def _request_id_headers(request_id: str | None) -> dict[str, str] | None:
    return {REQUEST_ID_HEADER: request_id} if request_id else None


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # 예상 가능한 4xx: stack trace는 남기지 않되, 필드별 원인은 진단용으로 로깅
    request_id = get_request_id(request)
    logger.warning(
        "validation failed: request_id=%s path=%s errors=%s",
        request_id,
        request.url.path,
        exc.errors(),
    )
    # 이 경로는 RequestIDMiddleware를 정상적으로 거치므로 헤더는 미들웨어가 붙인다 (중복 방지)
    return JSONResponse(
        status_code=COMMON_INVALID_REQUEST.status,
        content=error_body(COMMON_INVALID_REQUEST, request.url.path, request_id),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # 예상치 못한 실패: 원본 예외는 로그에 보존하고, 응답에는 안전한 메시지만 노출
    # 주의: 이 핸들러는 ServerErrorMiddleware가 미들웨어 스택 전체를 건너뛰고
    # 직접 호출하므로, 헤더는 반드시 여기서 응답 객체에 직접 실어야 한다.
    request_id = get_request_id(request)
    logger.exception(
        "unhandled exception: request_id= %s path= %s", request_id, request.url.path
    )
    return JSONResponse(
        status_code=COMMON_INTERNAL_SERVER_ERROR.status,
        content=error_body(COMMON_INTERNAL_SERVER_ERROR, request.url.path, request_id),
        headers=_request_id_headers(request_id),
    )


@app.get("/health", tags=["health"])
def health():
    if not is_loaded():
        # 503 = Service Unavailable
        # Gateway, Eureka가 상태코드로 판단한다
        return JSONResponse(status_code=503, content={"status": "DOWN"})

    return {"status": "UP", "modelVersion": get_predictor().version}
