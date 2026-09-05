"""Request ID 응답 헤더와 접근 이벤트의 회귀 검증."""

import logging
import re

VALID_REQUEST_ID = re.compile(r"^[0-9a-f]{32}$")


def test_empty_header_treated_as_missing(client):
    response = client.get("/health", headers={"X-Request-ID": ""})

    assert VALID_REQUEST_ID.fullmatch(response.headers["x-request-id"])


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
        if r.name == "app.request_id" and request_id in r.message
    ]

    assert len(matched) == 1
    assert " 500 " in matched[0].message
