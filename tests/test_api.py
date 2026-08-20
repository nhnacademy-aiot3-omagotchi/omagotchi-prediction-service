"""
HTTP 경계 테스트

200/400/500을 TestClient로 검증
500은 실제 모델을 망가뜨리지 않고 FastAPI의 dependecy_overrides로 가짜 predictor를 주입해서 유발함 (스프링의 @MockBean 같은 것)
(권한 실패는 인증 안 붙인 상태라 아직 없음)
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.predictor import get_predictor

VALID_PAYLOAD = {
    "studyLag1": 9.5978,  # 오늘 공부량 (예측 당시의 어제)
    "studyLag2": 9.6236,
    "studyLag3": 8.1269,
    "study7dMean": 7.3602,
    "study30dMean": 6.9199,
    "studyAllMean": 6.7323,
    "study7dStd": 3.5685,
    "trend7To30": 0.4403,
    "studyDiff1d": -0.0258,
    "att7d": 1.0,
    "att30d": 0.9545,
    "attAll": 0.9767,
    "attendDays7d": 6.0,
    "noshowYesterday": 0,
    "late7d": 0.0,
    "late30d": 0.0,
    "lateAll": 0.0238,
    "forgot7d": 0.0,
    "entryLag1Min": 540.0,
    "entry7dMeanMin": 539.1667,
    "level": 18,
    "questsTotal": 142,
    "questStreak": 2,
    "questRate7d": 0.5714,
    "tomorrowIsWeekday": 0,
    "tomorrowDow1": 0,
    "tomorrowDow2": 0,
    "tomorrowDow3": 0,
    "tomorrowDow4": 0,
    "tomorrowDow5": 1,
    "tomorrowDow6": 0,
    "daysSinceStart": 298,
}


@pytest.fixture
def client():

    # raise_server_exceptions=False: 500도 응답으로 받아서 검사하기 위해 켰음
    # (기본값 True면 ServerErrorMiddleware가 재발생시키는 예외가 테스트를 실패시킴)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    app.dependency_overrides.clear()  # 다음 테스트로 새지 않게 정리


def test_predict_success(client):
    response = client.post("/api/v1/predictions/study-time", json=VALID_PAYLOAD)

    assert response.status_code == 200

    body = response.json()

    assert body["predictedStudyHours"] == 2.178
    assert body["modelVersion"]


def test_predict_validation_failure_returns_error_format(client):
    response = client.post("/api/v1/predictions/study-time", json={"studyLag1": 5.0})

    assert response.status_code == 400

    body = response.json()

    assert body["code"] == "COMMON_INVALID_REQUEST"
    assert body["path"] == "/api/v1/predictions/study-time"


def test_predict_unhandled_exception_returns_error_format(client):

    # 가짜 predictor
    def broken_predictor():
        class Broken:
            version = "broken"

            def predict(self, features):
                raise RuntimeError("테스트용 강제 예외")

        return Broken()

    app.dependency_overrides[get_predictor] = broken_predictor

    response = client.post("/api/v1/predictions/study-time", json=VALID_PAYLOAD)

    assert response.status_code == 500

    body = response.json()

    assert body["code"] == "COMMON_INTERNAL_SERVER_ERROR"


def test_request_id_echoed_in_header_and_body(client):
    response = client.post(
        "/api/v1/predictions/study-time",
        json={"studyLag1": 5.0},
        headers={"X-Request-ID": "test-fixed-id"},
    )

    assert response.headers["x-request-id"] == "test-fixed-id"
    assert response.json()["requestId"] == "test-fixed-id"


def test_request_id_generated_when_missing(client):
    response = client.get("/health")

    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 0
