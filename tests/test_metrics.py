"""HTTP 메트릭의 요청 집계·원본 URL 제외 검증."""

from prometheus_client.parser import text_string_to_metric_families


def test_http_metrics_use_route_and_status_without_raw_input(client, service_auth):
    # Given: 실제 Trace Sampling과 별개로 집계할 검증 실패 요청
    response = client.post(
        "/api/v1/predictions/study-time?token=not-a-real-secret",
        json={},
        auth=service_auth,
        headers={"traceparent": "00-11111111111111111111111111111111-2222222222222222-00"},
    )

    # When
    scrape = client.get("/metrics")
    samples = [sample for family in text_string_to_metric_families(scrape.text) for sample in family.samples]

    # Then: 미샘플 요청도 집계, 고정 Route와 상태만 포함
    assert response.status_code == 400
    assert scrape.status_code == 200
    assert "not-a-real-secret" not in scrape.text
    counts = [sample for sample in samples if sample.name == "http_server_requests_seconds_count"
              and sample.labels.get("http_route") == "/api/v1/predictions/study-time"
              and sample.labels.get("http_response_status_code") == "400"]
    assert counts and counts[0].value >= 1
    assert set(counts[0].labels) == {"http_request_method", "http_route", "http_response_status_code"}


def test_health_and_metrics_are_not_counted_or_access_logged(client, caplog):
    # Given
    before = client.get("/metrics").text

    # When
    client.get("/health")
    after = client.get("/metrics").text

    # Then: 자체 수집으로 HTTP 수치·접근 이벤트를 계속 추가하지 않는 구성
    before_http = [line for line in before.splitlines() if line.startswith("http_server_requests_")]
    after_http = [line for line in after.splitlines() if line.startswith("http_server_requests_")]
    assert before_http == after_http
    assert not any(record.name == "app.request_id" for record in caplog.records)
