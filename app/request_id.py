"""
Request ID 전파 미들웨어
- 들어온 X-Request-ID가 있으면 그대로 전파 (형식을 해석하지 않는 opaque 문자열)
- 없거나 빈 값이면 이 서비스가 요청 경계로서 새로 발급
- 응답 헤더 X-Request-ID, 오류 응답의 requestId, 로그가 전부 같은 값을 쓴다

값은 scope["state"](=request.state)에 저장한다 (contextvars 아님).
Starlette의 raw Exception 핸들러(ServerErrorMiddleware)는 사용자 미들웨어 스택
전체를 건너뛰고 최상위 send로 직접 응답을 내보내기 때문에, 이 경로에서는
1) 미들웨어의 send 래핑이 아예 호출되지 않고
2) contextvars도 그 경로에서 새로 구성되는 실행 흐름에서 보장되지 않는다.
scope는 요청 전체(정상 처리·예외 처리 모두)가 공유하는 같은 딕셔너리라서
어느 경로로 응답이 나가든 값을 읽을 수 있는 유일하게 신뢰할 수 있는 방법이다.
그래서 응답 헤더도 미들웨어가 아니라 각 예외 핸들러가 직접 부착한다 (app/main.py).

완료 로그(요청당 한 줄)도 같은 이유로 try/finally 안에서 남긴다 —
처리되지 않은 예외는 self.app() 호출 자체를 뚫고 나가므로, finally 없이
로그를 뒤에 두면 500 케이스에서만 로그가 통째로 빠진다.
"""

import logging
import time
import uuid

from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_STATE_KEY = "request_id"

logger = logging.getLogger(__name__)


class RequestIDMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        incoming = headers.get(REQUEST_ID_HEADER)
        request_id = incoming if incoming else uuid.uuid4().hex

        scope.setdefault("state", {})[REQUEST_ID_STATE_KEY] = request_id

        started_at = time.monotonic()
        status_holder = {"status": None}

        async def send_wrapper(message: Message) -> None:
            # 정상 경로(라우트 핸들러가 만든 응답)는 여기를 거친다
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                raw_headers = list(message.get("headers", []))
                already_has_id = any(
                    k.lower() == REQUEST_ID_HEADER.lower().encode("latin-1")
                    for k, _ in raw_headers
                )

                if not already_has_id:
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


def get_request_id(request: Request) -> str | None:
    # request.state에서 Request ID를 꺼낸다
    return getattr(request.state, REQUEST_ID_STATE_KEY, None)
