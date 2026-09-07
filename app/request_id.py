"""Request ID 확정·전파와 HTTP 접근 이벤트 기록."""

from contextvars import ContextVar
import logging
import re
import time
import uuid

from opentelemetry import trace
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_STATE_KEY = "request_id"
TRACE_ID_STATE_KEY = "trace_id"
SPAN_ID_STATE_KEY = "span_id"

_VALID_REQUEST_ID = re.compile(r"^[0-9a-f]{32}$")
_current_request_id: ContextVar[str | None] = ContextVar(
    "http.request.id", default=None
)

logger = logging.getLogger(__name__)


class RequestIDMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        incoming_values = headers.getlist(REQUEST_ID_HEADER)
        request_id = (
            incoming_values[0]
            if len(incoming_values) == 1
            and _VALID_REQUEST_ID.fullmatch(incoming_values[0]) is not None
            else uuid.uuid4().hex
        )

        state = scope.setdefault("state", {})
        state[REQUEST_ID_STATE_KEY] = request_id
        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            state[TRACE_ID_STATE_KEY] = format(span_context.trace_id, "032x")
            state[SPAN_ID_STATE_KEY] = format(span_context.span_id, "016x")

        token = _current_request_id.set(request_id)
        started_at = time.monotonic_ns()
        status_code: int | None = None

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                raw_headers = list(message.get("headers", []))
                request_id_header = REQUEST_ID_HEADER.lower().encode("latin-1")
                raw_headers = [
                    (name, value)
                    for name, value in raw_headers
                    if name.lower() != request_id_header
                ]
                raw_headers.append(
                    (
                        REQUEST_ID_HEADER.encode("latin-1"),
                        request_id.encode("latin-1"),
                    )
                )
                message["headers"] = raw_headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            if scope["path"] not in {"/health", "/metrics"}:
                completed_status = status_code or 500
                route = getattr(scope.get("route"), "path", "UNMATCHED")
                extra = {
                    "event": {
                        "dataset": "prediction-service.http",
                        "action": "http.server.request.completed",
                        "outcome": "failure" if completed_status >= 400 else "success",
                        "duration": max(0, time.monotonic_ns() - started_at),
                    },
                    "http": {
                        "request": {"id": request_id, "method": scope["method"]},
                        "response": {"status_code": completed_status},
                    },
                    "omagotchi": {"http": {"route": route}},
                }
                if TRACE_ID_STATE_KEY in state:
                    extra["trace"] = {"id": state[TRACE_ID_STATE_KEY]}
                    extra["span"] = {"id": state[SPAN_ID_STATE_KEY]}
                logger.log(
                    logging.ERROR if completed_status >= 500 else logging.INFO,
                    "HTTP request completed",
                    extra=extra,
                )
            _current_request_id.reset(token)


def current_request_id() -> str | None:
    """현재 비동기 실행 문맥의 Request ID 조회."""
    return _current_request_id.get()


def get_request_id(request: Request) -> str | None:
    """예외 처리까지 유지되는 요청 상태의 Request ID 조회."""
    return getattr(request.state, REQUEST_ID_STATE_KEY, None)
