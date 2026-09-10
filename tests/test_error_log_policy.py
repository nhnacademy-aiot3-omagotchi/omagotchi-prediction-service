"""예상 가능한 4xx와 예상하지 못한 5xx의 로그 정책 검증."""

import json
import logging

import ecs_logging


def test_validation_failure_does_not_log_stack_trace(client, service_auth, caplog):
    with caplog.at_level(logging.WARNING, logger="app.exception_handlers"):
        client.post(
            "/api/v1/predictions/study-time",
            json={"studyLag1": 5.0},
            auth=service_auth,
        )

    records = [r for r in caplog.records if r.name == "app.exception_handlers"]

    assert records == []


def test_unhandled_exception_logs_stack_trace(
    client, api_payload, service_auth, broken_predictor_installed, caplog
):
    with caplog.at_level(logging.WARNING, logger="app.exception_handlers"):
        client.post(
            "/api/v1/predictions/study-time", json=api_payload, auth=service_auth
        )

    records = [r for r in caplog.records if r.name == "app.exception_handlers"]

    assert len(records) == 2
    safe = next(record for record in records if record.event["dataset"] == "prediction-service.error")
    safe_document = json.loads(ecs_logging.StdlibFormatter().format(safe))
    assert safe.exc_info is None
    assert "RuntimeError" in safe_document["error"]["stack_trace"]
    assert "테스트용 강제 예외" not in json.dumps(safe_document, ensure_ascii=False)
    assert "message" not in safe_document["error"]
    assert {record.event["dataset"] for record in records} == {
        "prediction-service.error",
        "prediction-service.diagnostic",
    }
    diagnostic = next(
        record
        for record in records
        if record.event["dataset"] == "prediction-service.diagnostic"
    )
    assert diagnostic.exc_info is not None
    assert "RuntimeError" in caplog.text

    document = json.loads(
        ecs_logging.StdlibFormatter(stack_trace_limit=20).format(diagnostic)
    )
    assert document["error"]["type"] == "RuntimeError"
    assert document["error"]["message"] == "테스트용 강제 예외"
    assert document["error"]["stack_trace"]
