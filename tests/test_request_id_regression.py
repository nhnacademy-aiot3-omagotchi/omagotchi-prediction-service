"""Request ID 응답 헤더와 접근 이벤트의 회귀 검증."""

import logging
import re

import pytest

VALID_REQUEST_ID = re.compile(r"^[0-9a-f]{32}$")


@pytest.mark.parametrize("request_id", ["Dev-Request_01.test", "Z", "A" * 32])
def test_safe_header_preserved_in_response_and_access_log(client, service_auth, caplog, request_id):
    # Given: 생성 형식과 다르지만 허용 문자·길이를 만족하는 단일 ID
    with caplog.at_level(logging.INFO, logger="app.request_id"):
        # When
        response = client.post(
            "/api/v1/predictions/study-time",
            json={"studyLag1": 5.0},
            headers={"X-Request-ID": request_id},
            auth=service_auth,
        )

    # Then: 응답과 접근 로그의 동일한 값, 불필요한 교체 경고 없음
    assert response.headers.get_list("x-request-id") == [request_id]
    events = [record for record in caplog.records if record.name == "app.request_id"]
    assert len(events) == 1
    assert events[0].http["request"]["id"] == request_id
    assert events[0].levelno == logging.INFO


def test_long_safe_header_keeps_prefix_without_logging_original(client, service_auth, caplog):
    # Given
    original = "Dev-Request_0123456789.abcdefghijk-privateSuffix"
    expected = original[:32]
    with caplog.at_level(logging.INFO, logger="app.request_id"):
        # When
        response = client.post(
            "/api/v1/predictions/study-time",
            json={"studyLag1": 5.0},
            headers={"X-Request-ID": original},
            auth=service_auth,
        )

    # Then: 접근 로그·응답·경고의 확정값 일치, 경고 한 번과 원문 제외
    assert response.headers.get_list("x-request-id") == [expected]
    events = [record for record in caplog.records if record.name == "app.request_id"]
    assert len(events) == 2
    assert all(record.http["request"]["id"] == expected for record in events)
    warnings = [record for record in events if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "length limit exceeded" in warnings[0].getMessage()
    assert "privateSuffix" not in caplog.text


@pytest.mark.parametrize("request_id", ["invalid request id", "first,second", "a" * 32 + "!", "a" * 32 + "\n"])
def test_unsafe_header_is_not_truncated_or_echoed(client, caplog, request_id):
    # Given
    with caplog.at_level(logging.WARNING, logger="app.request_id"):
        # When
        response = client.get("/health", headers={"X-Request-ID": request_id})

    # Then: 전체 문자 검사 후 신규 ID 발급, 원문 미기록
    resolved = response.headers["x-request-id"]
    assert VALID_REQUEST_ID.fullmatch(resolved)
    assert resolved != request_id[:32]
    warnings = [record for record in caplog.records if record.name == "app.request_id"]
    assert len(warnings) == 1
    assert warnings[0].http["request"]["id"] == resolved
    assert request_id not in warnings[0].getMessage()


def test_empty_header_treated_as_missing(client, caplog):
    response = client.get("/health", headers={"X-Request-ID": ""})

    assert VALID_REQUEST_ID.fullmatch(response.headers["x-request-id"])
    assert not [record for record in caplog.records if record.name == "app.request_id"]


def test_valid_header_not_duplicated_on_validation_failure(client, service_auth):
    request_id = "0123456789abcdef0123456789abcdef"
    response = client.post(
        "/api/v1/predictions/study-time",
        json={"studyLag1": 5.0},
        headers={"X-Request-ID": request_id},
        auth=service_auth,
    )

    assert response.headers.get_list("x-request-id") == [request_id]


def test_duplicate_headers_replaced_with_one_generated_value(client):
    response = client.get(
        "/health",
        headers=[
            ("X-Request-ID", "0123456789abcdef0123456789abcdef"),
            ("X-Request-ID", "abcdef0123456789abcdef0123456789"),
        ],
    )

    request_ids = response.headers.get_list("x-request-id")
    assert len(request_ids) == 1
    assert VALID_REQUEST_ID.fullmatch(request_ids[0])


def test_header_present_on_unhandled_exception(
    client, api_payload, service_auth, broken_predictor_installed
):
    request_id = "11111111111111111111111111111111"
    response = client.post(
        "/api/v1/predictions/study-time",
        json=api_payload,
        headers={"X-Request-ID": request_id},
        auth=service_auth,
    )

    assert response.status_code == 500
    assert response.headers.get_list("x-request-id") == [request_id]


def test_completion_log_fires_on_unhandled_exception(
    client, api_payload, service_auth, broken_predictor_installed, caplog
):
    request_id = "22222222222222222222222222222222"
    with caplog.at_level(logging.INFO, logger="app.request_id"):
        client.post(
            "/api/v1/predictions/study-time",
            json=api_payload,
            headers={"X-Request-ID": request_id},
            auth=service_auth,
        )

    matched = [
        r
        for r in caplog.records
        if r.name == "app.request_id"
        and getattr(r, "event", {}).get("dataset") == "prediction-service.http"
    ]

    assert len(matched) == 1
    assert matched[0].http["request"]["id"] == request_id
    assert matched[0].http["response"]["status_code"] == 500
