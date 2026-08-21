"""
애플리케이션 기동 테스트
"""

from fastapi.testclient import TestClient

import app.main as main_module
import app.predictor as predictor_module


# client fixture 자체가 TestClient(app)를 with로 여는 거라서, 이 fixture를 받는 순간 lifespan(모델 로드)이 실행됨
# Spring의 @SpringBootTest(컨텍스트가 뜨는가)와 비슷한 성격의 테스트
def test_app_starts_and_loads_model(client):
    response = client.get("/health")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "UP"
    assert body["modelVersion"]  # 빈 문자열이 아니어야 함


# 모델 로드가 실패해도 앱 기동 자체는 죽지 않고 /health가 503을 보고해야 함
# (수정 전에는 load_predictor()의 예외가 lifespan을 뚫고 나가서 TestClient 진입 자체가 실패했음)
def test_app_survives_model_load_failure(monkeypatch):
    # _predictor를 먼저 비워서 진짜 로드가 안 된 상태를 흉내내기
    monkeypatch.setattr(predictor_module, "_predictor", None)

    # load_predictor 자체가 실패하는 상황 재현
    def boom(path):
        raise RuntimeError("모델 파일을 찾을 수 없음")

    monkeypatch.setattr(main_module, "load_predictor", boom)

    # conftest.py의 client fixture를 안 쓰고 직접 TestClient를 열음
    # monkeypatch(가짜 load_payload)를 TestClient 진입(= lifespan 실행) 전에 미리 걸어둬야 하기 때문
    # client fixture는 이미 열려있는 걸 받는 구조라 이 순서를 맞출 수 없음
    # 여기서 예외 없이 컨텍스트 진입에 성공해야 함
    with TestClient(main_module.app) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "DOWN"
