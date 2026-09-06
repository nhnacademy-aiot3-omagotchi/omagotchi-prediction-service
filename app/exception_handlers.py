"""FastAPI 공통 HTTP 예외 처리기."""

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.errors import (
    AUTH_AUTHENTICATION_REQUIRED,
    COMMON_INTERNAL_SERVER_ERROR,
    COMMON_INVALID_REQUEST,
    error_body,
)
from app.security import REALM, AuthenticationRequiredError

from app.request_id import (
    REQUEST_ID_HEADER,
    SPAN_ID_STATE_KEY,
    TRACE_ID_STATE_KEY,
    get_request_id,
)

logger = logging.getLogger(__name__)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = get_request_id(request)
    return JSONResponse(
        status_code=COMMON_INVALID_REQUEST.status,
        content=error_body(COMMON_INVALID_REQUEST, request.url.path, request_id),
    )


async def authentication_exception_handler(
    request: Request, exc: AuthenticationRequiredError
):
    request_id = get_request_id(request)
    return JSONResponse(
        status_code=AUTH_AUTHENTICATION_REQUIRED.status,
        content=error_body(AUTH_AUTHENTICATION_REQUIRED, request.url.path, request_id),
        headers={"WWW-Authenticate": f'Basic realm="{REALM}", charset="UTF-8"'},
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = get_request_id(request)
    event_id = str(uuid.uuid4())
    route = getattr(request.scope.get("route"), "path", "UNMATCHED")
    shared_context = {
        "event": {
            "id": event_id,
            "action": "http.server.request.failed",
            "outcome": "failure",
        },
        "http": {
            "request": {"id": request_id, "method": request.method},
            "response": {"status_code": COMMON_INTERNAL_SERVER_ERROR.status},
        },
        "omagotchi": {"http": {"route": route}},
    }
    trace_id = getattr(request.state, TRACE_ID_STATE_KEY, None)
    span_id = getattr(request.state, SPAN_ID_STATE_KEY, None)
    if trace_id is not None and span_id is not None:
        shared_context["trace"] = {"id": trace_id}
        shared_context["span"] = {"id": span_id}

    logger.error(
        "HTTP server error",
        extra={
            **shared_context,
            "event": {
                **shared_context["event"],
                "dataset": "prediction-service.error",
            },
            "error": {
                "code": COMMON_INTERNAL_SERVER_ERROR.code,
                "type": f"{type(exc).__module__}.{type(exc).__qualname__}",
            },
        },
    )
    logger.error(
        "HTTP server failure diagnostic",
        exc_info=(type(exc), exc, exc.__traceback__),
        extra={
            **shared_context,
            "event": {
                **shared_context["event"],
                "dataset": "prediction-service.diagnostic",
            },
        },
    )
    return JSONResponse(
        status_code=COMMON_INTERNAL_SERVER_ERROR.status,
        content=error_body(COMMON_INTERNAL_SERVER_ERROR, request.url.path, request_id),
        headers={REQUEST_ID_HEADER: request_id} if request_id else None,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """공통 HTTP 예외 처리기 등록."""
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.add_exception_handler(
        AuthenticationRequiredError,
        authentication_exception_handler
    )
