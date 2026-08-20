"""
Request ID 미들웨어 회귀 테스트
(500 헤더 누락, 헤더 중복, 500 완료 로그 누락) -> 재발 방지 위해서

client, api_payload, broken_predictor_installed fixture는 conftext.py에 있음
"""

import logging


def test_empty_header_treated_as_missing(client):
    response = client.get("/health", headers={"X-Request-ID": ""})

    assert response.headers["x-request-id"] != ""


def test_header_not_duplicated_on_validation_failure(client):
    response = client.post(
        "/api/v1/predictions/study-time",
        json={"studyLag1": 5.0},
        headers={"X-Request-ID": "duplicate-check-400"},
    )

    assert response.headers.get_list("x-request-id") == ["duplicate-check-400"]


def test_header_present_on_unhandled_exception(
    client, api_payload, broken_predictor_installed
):
    response = client.post(
        "/api/v1/predictions/study-time",
        json=api_payload,
        headers={"X-Request-ID": "header-check-500"},
    )

    assert response.status_code == 500
    assert response.headers.get_list("x-request-id") == ["header-check-500"]


def test_completion_log_fires_on_unhandled_exception(
    client, api_payload, broken_predictor_installed, caplog
):
    with caplog.at_level(logging.INFO, logger="app.request_id"):
        client.post(
            "/api/v1/predictions/study-time",
            json=api_payload,
            headers={"X-Request-ID": "completion-log-check"},
        )

    matched = [
        r
        for r in caplog.records
        if r.name == "app.request_id" and "completion-log-check" in r.message
    ]

    assert len(matched) == 1
    assert " 500 " in matched[0].message
