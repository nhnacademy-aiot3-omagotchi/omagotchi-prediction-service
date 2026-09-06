"""W3C Trace Context 수신과 접근 이벤트 연결 검증."""

import logging


def test_incoming_traceparent_connects_access_event(client, service_auth, caplog):
    trace_id = "11111111111111111111111111111111"
    parent_span_id = "2222222222222222"
    request_id = "33333333333333333333333333333333"

    # Given: Nginx·Learning에서 이어진 W3C Trace Context와 Request ID
    with caplog.at_level(logging.INFO, logger="app.request_id"):
        # When: 검증 오류로 종료되는 Prediction HTTP 요청
        response = client.post(
            "/api/v1/predictions/study-time",
            json={"studyLag1": 5.0},
            headers={
                "traceparent": f"00-{trace_id}-{parent_span_id}-01",
                "X-Request-ID": request_id,
            },
            auth=service_auth,
        )

    # Then: 같은 Trace·Request ID와 새 서버 Span을 포함한 접근 이벤트
    assert response.status_code == 400
    event = next(
        record
        for record in caplog.records
        if record.name == "app.request_id"
        and getattr(record, "event", {}).get("dataset") == "prediction-service.http"
        and record.http["request"]["id"] == request_id
    )
    assert event.trace["id"] == trace_id
    assert len(event.span["id"]) == 16
    assert event.span["id"] != parent_span_id
    assert event.omagotchi["http"]["route"] == "/api/v1/predictions/study-time"
