"""
애플리케이션 기동 테스트
"""

import pytest
from fastapi.testclient import TestClient

import app.main as main_module


# client fixture 자체가 TestClient(app)를 with로 여는 거라서, 이 fixture를 받는 순간 lifespan(모델 로드)이 실행됨
# Spring의 @SpringBootTest(컨텍스트가 뜨는가)와 비슷한 성격의 테스트
def test_app_starts_and_loads_model(client):
    response = client.get("/health")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "UP"
    assert body["modelVersion"]  # 빈 문자열이 아니어야 함


# 모델은 prediction-service의 필수 리소스이므로, 로드 실패하면 원본 예외를 그대로 전파해서 기동 자체를 실패시켜야 함
def test_app_fails_to_start_when_model_load_fails(monkeypatch):
    def boom(path):
        raise RuntimeError("모델 파일을 찾을 수 없음")

    monkeypatch.setattr(main_module, "load_predictor", boom)

    with pytest.raises(RuntimeError), TestClient(main_module.app):
        pass
