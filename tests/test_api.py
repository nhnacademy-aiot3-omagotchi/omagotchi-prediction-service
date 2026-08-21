"""
HTTP 경계 테스트

200/400/500을 TestClient로 검증
500은 실제 모델을 망가뜨리지 않고 FastAPI의 dependecy_overrides로 가짜 predictor를 주입해서 유발함 (스프링의 @MockBean 같은 것)
(권한 실패는 인증 안 붙인 상태라 아직 없음)

client, api_payload, broken_predictor_installed fixture는 conftest.py에 있음
"""

import app.predictor as predictor_module


def test_predict_success(client, api_payload):
    response = client.post("/api/v1/predictions/study-time", json=api_payload)

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


def test_predict_unhandled_exception_returns_error_format(
    client, api_payload, broken_predictor_installed
):
    response = client.post("/api/v1/predictions/study-time", json=api_payload)

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


# /health의 503 분기
# 앱이 이미 뜬 뒤에 _predictor를 억지로 None으로 되돌리는 방식이라 로드 자체가 실패하는 상황은 검증 못 함
def test_health_returns_down_when_model_not_loaded(client, monkeypatch):
    monkeypatch.setattr(predictor_module, "_predictor", None)

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "DOWN"
