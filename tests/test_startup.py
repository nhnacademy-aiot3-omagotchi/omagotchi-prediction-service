"""
애플리케이션 기동 테스트
"""


# client fixture 자체가 TestClient(app)를 with로 여는 거라서, 이 fixture를 받는 순간 lifespan(모델 로드)이 실행됨
# Spring의 @SpringBootTest(컨텍스트가 뜨는가)와 비슷한 성격의 테스트
def test_app_starts_and_loads_model(client):
    response = client.get("/health")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "UP"
    assert body["modelVersion"]  # 빈 문자열이 아니어야 함
