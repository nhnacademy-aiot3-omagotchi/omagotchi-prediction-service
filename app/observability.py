"""Prediction 서비스의 구조화 로그와 W3C Trace Context 설정."""

import logging
import os
import sys

import ecs_logging
from opentelemetry import propagate, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

_configured = False


class _ObservabilityContextFilter(logging.Filter):
    """모든 로그에 서비스 식별자와 현재 HTTP 상관관계 식별자 추가."""

    def __init__(self) -> None:
        super().__init__()
        self._service = {
            "name": "prediction-service",
            "version": os.getenv("SERVICE_VERSION", "unknown"),
            "environment": os.getenv("SERVICE_ENVIRONMENT", "local"),
            "node": {"name": os.getenv("SERVICE_NODE_NAME", "prediction-service")},
        }

    def filter(self, record: logging.LogRecord) -> bool:
        record.__dict__.setdefault("service", self._service)

        from app.request_id import current_request_id

        request_id = current_request_id()
        if request_id is not None:
            record.__dict__.setdefault("http", {"request": {"id": request_id}})

        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            record.__dict__.setdefault("trace", {"id": format(span_context.trace_id, "032x")})
            record.__dict__.setdefault("span", {"id": format(span_context.span_id, "016x")})
        return True


def configure_observability() -> None:
    """프로세스 전역 로그와 Trace Context 전파 설정."""
    global _configured
    if _configured:
        return

    provider = TracerProvider(
        resource=Resource.create({"service.name": "prediction-service"})
    )
    trace.set_tracer_provider(provider)
    # Baggage를 제외한 W3C Trace Context만 수신·전파
    propagate.set_global_textmap(TraceContextTextMapPropagator())

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_ObservabilityContextFilter())
    handler.setFormatter(ecs_logging.StdlibFormatter(stack_trace_limit=20))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    # 요청 URL 전체를 INFO 메시지로 기록하는 HTTPX 로그 억제
    for logger_name in ("httpx", "httpx2"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Uvicorn 기동·오류 로그의 ECS 핸들러 일원화
    for logger_name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    # 구조화 접근 이벤트와 중복되는 Uvicorn 기본 접근 로그 비활성화
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.handlers.clear()
    uvicorn_access_logger.propagate = False
    _configured = True
