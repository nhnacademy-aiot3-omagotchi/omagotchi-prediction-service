"""
서비스 인증 경계 테스트
ADR 0013 §9: Credential 누락·오답·정답을 각각 검증한다

client, api_payload, service_auth fixture는 conftest.py에 있음
"""

import pytest

from app.security import REALM


def test_missing_credential_rejected(client, api_payload):
    response = client.post("/api/v1/predictions/study-time", json=api_payload)

    assert response.status_code == 401

    body = response.json()

    assert body["code"] == "AUTH_AUTHENTICATION_REQUIRED"
    assert body["path"] == "/api/v1/predictions/study-time"
    assert REALM in response.headers["www-authenticate"]


@pytest.mark.parametrize(
    "bad_auth",
    [
        ("wrong-user", "test-credential-for-pytest-only-000000"),
        ("learning-service", "wrong-password-wrong-password-000000"),
    ],
    ids=["wrong-username", "wrong-password"],
)
def test_wrong_credential_rejected(client, api_payload, bad_auth):
    response = client.post(
        "/api/v1/predictions/study-time", json=api_payload, auth=bad_auth
    )

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_AUTHENTICATION_REQUIRED"


# HTTPBasic이 auto_error=False를 무시하고 자체 HTTPException을 던지는 입력들.
# 그대로 두면 {"detail": ...} 형식이 나가므로 우리 예외 핸들러로 모아야 한다.
@pytest.mark.parametrize(
    "authorization",
    [
        "Basic !!!not-base64!!!",
        "Basic ",
        "Basic bm9jb2xvbg==",  # base64는 정상이지만 'nocolon' — ':' 구분자가 없음
        "Bearer some-token",
        "Basic",
    ],
    ids=["broken-base64", "empty-param", "no-colon", "wrong-scheme", "scheme-only"],
)
def test_malformed_authorization_header_returns_contract_error(
    client, api_payload, authorization
):
    response = client.post(
        "/api/v1/predictions/study-time",
        json=api_payload,
        headers={"Authorization": authorization},
    )

    assert response.status_code == 401

    body = response.json()

    # FastAPI 기본 형식({"detail": ...})이 아니라 ADR 0012 형식이어야 한다
    assert body["code"] == "AUTH_AUTHENTICATION_REQUIRED"
    assert body["path"] == "/api/v1/predictions/study-time"
    assert "detail" not in body
    assert REALM in response.headers["www-authenticate"]


def test_correct_credential_accepted(client, api_payload, service_auth):
    response = client.post(
        "/api/v1/predictions/study-time", json=api_payload, auth=service_auth
    )

    assert response.status_code == 200


def test_health_does_not_require_credential(client):
    # Compose healthcheck가 Credential 없이 호출하므로 인증 대상에서 제외한다
    response = client.get("/health")

    assert response.status_code == 200


def test_credential_not_exposed_in_error_response(client, api_payload):
    # 시도된 Credential이 응답 본문으로 새어나가지 않아야 한다
    response = client.post(
        "/api/v1/predictions/study-time",
        json=api_payload,
        auth=("learning-service", "wrong-password-wrong-password-000000"),
    )

    assert "wrong-password" not in response.text


def test_credential_repr_redacts_password():
    # 로그나 예외 메시지에 password가 남지 않아야 한다 (ADR 0013)
    from app.security import ServiceCredential

    credential = ServiceCredential(username="learning-service", password="s3cr3t-value")

    assert "s3cr3t-value" not in repr(credential)
    assert "[REDACTED]" in repr(credential)
