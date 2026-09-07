"""Prediction 서비스의 구조화 로그·메트릭·W3C Trace 설정."""

import logging
import os
import sys

import ecs_logging
from opentelemetry import metrics, propagate, trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.view import DropAggregation, ExplicitBucketHistogramAggregation, View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanLimits, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
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
    """프로세스 전역 로그·메트릭·Trace 전파 및 전송 설정."""
    global _configured
    if _configured:
        return

    resource = Resource.create({
        "service.name": "prediction-service",
        "service.version": os.getenv("SERVICE_VERSION", "unknown"),
        "service.instance.id": os.getenv("SERVICE_NODE_NAME", "prediction-service"),
        "deployment.environment.name": (
            "production" if os.getenv("SERVICE_ENVIRONMENT") == "prod"
            else os.getenv("SERVICE_ENVIRONMENT", "local")
        ),
    })
    provider = TracerProvider(
        resource=resource,
        sampler=ParentBased(TraceIdRatioBased(float(os.getenv("TRACING_SAMPLING_PROBABILITY", "1.0")))),
        span_limits=SpanLimits(max_attributes=32, max_attribute_length=256, max_events=8),
    )
    # 기존 Provider에만 전송기 연결, Collector 장애와 업무 요청의 분리
    # SDK의 프로세스 종료 훅으로 배치 전송기 정리
    if os.getenv("TRACING_EXPORT_ENABLED", "false").lower() == "true":
        provider.add_span_processor(BatchSpanProcessor(
            OTLPSpanExporter(timeout=2),
            max_queue_size=256,
            max_export_batch_size=128,
            schedule_delay_millis=5000,
            export_timeout_millis=3000,
        ))
    trace.set_tracer_provider(provider)
    # Baggage를 제외한 W3C Trace Context만 수신·전파
    propagate.set_global_textmap(TraceContextTextMapPropagator())

    # 기존 FastAPI 자동 계측 재사용, HTTP 시간만 수집하고 원본 URL·Host Label 제외
    os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "http")
    metrics.set_meter_provider(MeterProvider(
        resource=resource,
        metric_readers=[PrometheusMetricReader(disable_target_info=True, scope_info_enabled=False)],
        views=[
            View(instrument_name="*", aggregation=DropAggregation()),
            View(
                instrument_name="http.server.request.duration",
                name="http.server.requests",
                attribute_keys={"http.request.method", "http.response.status_code", "http.route"},
                aggregation=ExplicitBucketHistogramAggregation(
                    boundaries=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60)
                ),
            ),
        ],
    ))

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
