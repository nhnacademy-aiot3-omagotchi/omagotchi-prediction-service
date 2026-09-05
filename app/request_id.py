"""Request ID 확정·전파와 HTTP 접근 로그 기록."""

from contextvars import ContextVar
import logging
import re
import time
import uuid

from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_STATE_KEY = "request_id"

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
        token = _current_request_id.set(request_id)

        started_at = time.monotonic()
        status_holder = {"status": None}

        async def send_wrapper(message: Message) -> None:
            # 정상 경로(라우트 핸들러가 만든 응답)는 여기를 거친다
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
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
            elapsed_ms = (time.monotonic() - started_at) * 1000
            logger.info(
                "%s %s -> %s (%.1fms) [%s]",
                scope["method"],
                scope["path"],
                status_holder["status"] or 500,
                elapsed_ms,
                request_id,
            )
            _current_request_id.reset(token)


def current_request_id() -> str | None:
    """현재 비동기 실행 문맥의 Request ID 조회."""
    return _current_request_id.get()


def get_request_id(request: Request) -> str | None:
    """예외 처리까지 유지되는 요청 상태의 Request ID 조회."""
    return getattr(request.state, REQUEST_ID_STATE_KEY, None)
