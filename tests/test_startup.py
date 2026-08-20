"""
애플리케이션 기동 테스트
"""

from fastapi.testclient import TestClient

from app.main import app


def test_app_starts_and_loads_model():
    # TestClient를 with로 쓰면 lifespan(모델 로드)이 실제로 실행됨
    # Spring의 @SpringBootTest(컨텍스트가 뜨는가)와 비슷한 성격의 테스트
    with TestClient(app) as client:
        response = client.get("/health")

        assert response.status_code == 200

        body = response.json()

        assert body["status"] == "UP"
        assert body["modelVersion"]  # 빈 문자열이 아니어야 함
