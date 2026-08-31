"""
공통 예외 핸들러
Spring과 대응시키면 @ControllerAdvice GlobalExceptionHandler
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.errors import (
    AUTH_AUTHENTICATION_REQUIRED,
    COMMON_INTERNAL_SERVER_ERROR,
    COMMON_INVALID_REQUEST,
    error_body
)
from app.security import REALM, AuthenticationRequiredError

from app.request_id import REQUEST_ID_HEADER, get_request_id

logger = logging.getLogger(__name__)


def _request_id_headers(request_id: str | None) -> dict[str, str] | None:
    return {REQUEST_ID_HEADER: request_id} if request_id else None


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # 예상 가능한 4xx: stack trace는 남기지 않되, 필드별 원인은 진단용으로 로깅
    request_id = get_request_id(request)
    logger.warning(
        "validation failed: request_id = %s path = %s errors = %s",
        request_id,
        request.url.path,
        exc.errors(),
    )

    # 이 경로는 RequestIDMiddleware를 정상적으로 거치므로 헤더는 미들웨어가 붙인다 (중복 방지)
    return JSONResponse(
        status_code=COMMON_INVALID_REQUEST.status,
        content=error_body(COMMON_INVALID_REQUEST, request.url.path, request_id),
    )


async def authentication_exception_handler(
        request: Request, exc: AuthenticationRequiredError
):
    # 예상 가능한 4xx: 스택 트레이스 안 남긴다
    # 시도된 Credential은 로깅하지 않는다
    request_id = get_request_id(request)
    logger.warning(
        "authentication failed: request_id = %s path = %s",
        request_id,
        request.url.path,
    )

    return JSONResponse(
        status_code=AUTH_AUTHENTICATION_REQUIRED.status,
        content=error_body(AUTH_AUTHENTICATION_REQUIRED, request.url.path, request_id),
        headers={"WWW-Authenticate": f'Basic realm="{REALM}", charset="UTF-8"'},
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    # 예상치 못한 실패: 원본 예외는 로그에 보존하고, 응답에는 안전한 메시지만 노출
    # 주의: 이 핸들러는 ServerErrorMiddleware가 미들웨어 스택 전체를 건너뛰고
    # 직접 호출하므로, 헤더는 반드시 여기서 응답 객체에 직접 실어야 한다.
    request_id = get_request_id(request)
    logger.exception(
        "unhandled exception: request_id = %s path = %s", request_id, request.url.path
    )
    return JSONResponse(
        status_code=COMMON_INTERNAL_SERVER_ERROR.status,
        content=error_body(COMMON_INTERNAL_SERVER_ERROR, request.url.path, request_id),
        headers=_request_id_headers(request_id),
    )


def register_exception_handlers(app: FastAPI) -> None:
    # main.py에서 app 생성 직후 한 번 호출한다(Spring의 @ControllerAdvice 자동 스캔 같은 것)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.add_exception_handler(
        AuthenticationRequiredError,
        authentication_exception_handler
    )
