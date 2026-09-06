"""Prediction HTTP 경계의 성공·검증 실패·내부 오류 응답 검증."""

import logging

from app.config import MAX_STUDY_H
from app.main import app
from app.predictor import PredictionCalculation, get_predictor


def test_predict_success(client, api_payload, service_auth, caplog):
    request_id = "0123456789abcdef0123456789abcdef"
    with caplog.at_level(logging.INFO, logger="app.routers.prediction"):
        response = client.post(
            "/api/v1/predictions/study-time",
            json=api_payload,
            headers={"X-Request-ID": request_id},
            auth=service_auth,
        )

    assert response.status_code == 200

    body = response.json()

    # 실제 모델(models/study_time_model.joblib)로 계산한 오프라인 기대값
    # 모델을 재학습해서 교체하면 이 값도 같이 갱신해야 함 (http/prediction.http에도 동일 기대값이 있음)
    assert body["predictedStudyHours"] == 2.178
    assert body["modelVersion"]
    assert "학습 시간 예측 완료:" in caplog.text
    assert "원본예측(rawPredictedStudyHours)=" in caplog.text
    assert "출력범위보정(adjustment)=보정 없음(NONE)" in caplog.text
    assert "응답반올림(responsePredictedStudyHours)=2.178시간" in caplog.text
    assert "내일요일(tomorrowDayOfWeek)=토요일(SATURDAY)" in caplog.text
    assert "평일여부(tomorrowIsWeekday)=아니오(0)" in caplog.text
    assert "추론시간(inferenceElapsedMs)=" in caplog.text
    assert f"요청ID(requestId)={request_id}" in caplog.text


def test_predict_min_clamp_logged_as_warning(
        client, api_payload, service_auth, caplog
):
    _install_predictor(-0.566, 0.0)

    with caplog.at_level(logging.WARNING, logger="app.routers.prediction"):
        response = client.post(
            "/api/v1/predictions/study-time",
            json=api_payload,
            auth=service_auth,
        )

    assert response.status_code == 200
    assert response.json()["predictedStudyHours"] == 0.0
    assert "원본예측(rawPredictedStudyHours)=-0.5660시간" in caplog.text
    assert "출력범위보정(adjustment)=최소 0시간 적용(MIN_CLAMP)" in caplog.text


def test_predict_max_clamp_logged_as_warning(
        client, api_payload, service_auth, caplog
):
    _install_predictor(15.0, MAX_STUDY_H)

    with caplog.at_level(logging.WARNING, logger="app.routers.prediction"):
        response = client.post(
            "/api/v1/predictions/study-time",
            json=api_payload,
            auth=service_auth,
        )

    assert response.status_code == 200
    assert response.json()["predictedStudyHours"] == MAX_STUDY_H
    assert "원본예측(rawPredictedStudyHours)=15.0000시간" in caplog.text
    assert "출력범위보정(adjustment)=최대 11.5시간 적용(MAX_CLAMP)" in caplog.text


def test_predict_validation_failure_returns_error_format(client, service_auth):
    response = client.post(
        "/api/v1/predictions/study-time", json={"studyLag1": 5.0}, auth=service_auth
    )

    assert response.status_code == 400

    body = response.json()

    assert body["code"] == "COMMON_INVALID_REQUEST"
    assert body["path"] == "/api/v1/predictions/study-time"


# 예측 중 오류를 발생시키는 의존성 교체 Fixture 실행을 위한 매개변수 유지
def test_predict_unhandled_exception_returns_error_format(
        client, api_payload, service_auth, broken_predictor_installed
):
    response = client.post(
        "/api/v1/predictions/study-time", json=api_payload, auth=service_auth
    )

    assert response.status_code == 500

    body = response.json()

    assert body["code"] == "COMMON_INTERNAL_SERVER_ERROR"


def test_request_id_echoed_in_header_and_body(client, service_auth):
    request_id = "0123456789abcdef0123456789abcdef"
    response = client.post(
        "/api/v1/predictions/study-time",
        json={"studyLag1": 5.0},
        headers={"X-Request-ID": request_id},
        auth=service_auth,
    )

    assert response.headers["x-request-id"] == request_id
    assert response.json()["requestId"] == request_id


def test_request_id_generated_when_missing(client):
    response = client.get("/health")

    assert len(response.headers.get_list("x-request-id")) == 1
    assert len(response.headers["x-request-id"]) == 32


def _install_predictor(raw_hours: float, clamped_hours: float) -> None:
    class StubPredictor:
        version = "test-model"

        def predict(self, features):
            return PredictionCalculation(raw_hours, clamped_hours)

    app.dependency_overrides[get_predictor] = StubPredictor
