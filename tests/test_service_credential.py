"""
서비스 Credential 설정 검증 테스트
learning-service의 RuleCredentialPropertiesTest에 대응한다.

잘못된 Credential 설정은 기동 자체를 실패시켜야 하므로,
HTTP 경계(test_security.py)와 분리해 설정 바인딩만 따로 검증한다.
"""

import pytest

import app.security as security_module
from app.security import (
    PASSWORD_ENV,
    USERNAME_ENV,
    ServiceCredential,
    _read_credential_from_env,
    get_service_credential,
)

VALID_USERNAME = "learning-service"
VALID_PASSWORD = "test-only-learning-prediction-pw-000"


@pytest.fixture
def env(monkeypatch):
    # 각 테스트가 원하는 값만 세팅하도록 먼저 비운다
    monkeypatch.delenv(USERNAME_ENV, raising=False)
    monkeypatch.delenv(PASSWORD_ENV, raising=False)
    return monkeypatch


def test_valid_credential_binds_and_redacts(env):
    env.setenv(USERNAME_ENV, VALID_USERNAME)
    env.setenv(PASSWORD_ENV, VALID_PASSWORD)

    credential = _read_credential_from_env()

    assert credential.username == VALID_USERNAME
    assert credential.password == VALID_PASSWORD
    # 로그나 예외 메시지에 그대로 찍히지 않아야 한다
    assert "[REDACTED]" in repr(credential)
    assert VALID_PASSWORD not in repr(credential)


def test_missing_username_rejected(env):
    env.setenv(PASSWORD_ENV, VALID_PASSWORD)

    with pytest.raises(ValueError, match=USERNAME_ENV):
        _read_credential_from_env()


def test_missing_password_rejected(env):
    env.setenv(USERNAME_ENV, VALID_USERNAME)

    with pytest.raises(ValueError, match=PASSWORD_ENV):
        _read_credential_from_env()


def test_username_with_colon_rejected(env):
    # HTTP Basic이 username:password로 구분하므로 ':'가 들어가면 안 된다
    env.setenv(USERNAME_ENV, "learning:service")
    env.setenv(PASSWORD_ENV, VALID_PASSWORD)

    with pytest.raises(ValueError, match="':'"):
        _read_credential_from_env()


@pytest.mark.parametrize("length", [31, 73], ids=["too-short", "too-long"])
def test_password_length_out_of_range_rejected(env, length):
    env.setenv(USERNAME_ENV, VALID_USERNAME)
    env.setenv(PASSWORD_ENV, "a" * length)

    with pytest.raises(ValueError, match="32자 이상"):
        _read_credential_from_env()


def test_password_with_unsupported_character_rejected(env):
    env.setenv(USERNAME_ENV, VALID_USERNAME)
    env.setenv(PASSWORD_ENV, "a" * 31 + "+")  # 길이는 32자로 맞추고 문자만 위반

    with pytest.raises(ValueError, match="영문자"):
        _read_credential_from_env()


def test_get_service_credential_raises_when_not_loaded(monkeypatch):
    # 기동 시 로드되므로 실제로는 도달하기 어렵지만, 계약을 잠가둔다
    monkeypatch.setattr(security_module, "_credential", None)

    with pytest.raises(RuntimeError):
        get_service_credential()


def test_service_credential_is_immutable():
    # 로드된 Credential이 런타임에 바뀌지 않아야 한다
    credential = ServiceCredential(username=VALID_USERNAME, password=VALID_PASSWORD)

    with pytest.raises(Exception):
        credential.password = "changed"
