"""
서비스 간 HTTP Basic 인증
learning-service -> prediction-service 호출 관계 전용 Credential 검증

Credential은 모델과 마찬가지로 기동 필수 리소스라, 없거나 형식이 어긋나면 lifespan에서 예외를 그대로 전파해 기동 자체를 실패시킨다.
"""

import os
import re
import secrets
from dataclasses import dataclass

from fastapi import HTTPException, Request
from fastapi.security import HTTPBasic

# WWW-Authenticate realm — omagotchi-{피호출자}-{호출자} (identity, learning과 같은 규칙)
REALM = "omagotchi-prediction-learning"

USERNAME_ENV = "LEARNING_PREDICTION_USERNAME"
PASSWORD_ENV = "LEARNING_PREDICTION_PASSWORD"

# 팀 공통 Credential 규약 (identity, learning의 CredentialProperties와 동일)
PASSWORD_MIN_LENGTH = 32
PASSWORD_MAX_LENGTH = 72
_PASSWORD_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

# HTTP Basic payload는 ASCII로 해석되므로(FastAPI HTTPBasic) username도 ASCII로 제한한다.
# 비-ASCII를 허용하면 설정 검증은 통과하고 호출만 401로 실패해 원인 파악이 어렵다.
# 0x21~0x7e(출력 가능한 ASCII)에서 구분자 ':'(0x3a)만 제외한다.
_USERNAME_PATTERN = re.compile(r"^[\x21-\x39\x3b-\x7e]+$")


class AuthenticationRequiredError(Exception):
    # 인증 실패. 응답 형식은 exception_handlers가 담당한다
    pass


@dataclass(frozen=True)
class ServiceCredential:
    username: str
    password: str

    def __repr__(self) -> str:
        # 로그나 예외 메시지에 Credential이 남지 않도록 (ADR 0013)
        return f"ServiceCredential(username={self.username!r}, password=[REDACTED])"


def _read_credential_from_env() -> ServiceCredential:
    username = os.environ.get(USERNAME_ENV, "")
    password = os.environ.get(PASSWORD_ENV, "")

    if not username:
        raise ValueError(f"{USERNAME_ENV}은 비어 있을 수 없습니다.")
    if ":" in username:
        # HTTP Basic이 username:password로 구분하므로 ':'를 허용하지 않는다
        raise ValueError(f"{USERNAME_ENV}에는 ':'를 사용할 수 없습니다.")
    if not _USERNAME_PATTERN.fullmatch(username):
        raise ValueError(
            f"{USERNAME_ENV}는 공백을 제외한 ASCII 출력 가능 문자만 사용할 수 있습니다."
        )
    if not password:
        raise ValueError(f"{PASSWORD_ENV}는 비어 있을 수 없습니다.")
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise ValueError(
            f"{PASSWORD_ENV}는 {PASSWORD_MIN_LENGTH}자 이상"
            f" {PASSWORD_MAX_LENGTH}자 이하여야 합니다."
        )
    if not _PASSWORD_PATTERN.fullmatch(password):
        raise ValueError(f"{PASSWORD_ENV}는 영문자·숫자·'-'·'_'만 사용할 수 있습니다.")

    return ServiceCredential(username=username, password=password)


_credential: ServiceCredential | None = None


def load_service_credential() -> None:
    # 앱 기동 시 1회 호출 (predictor와 같은 방식)
    global _credential
    _credential = _read_credential_from_env()


def get_service_credential() -> ServiceCredential:
    if _credential is None:
        raise RuntimeError("서비스 Credential이 로드되지 않았습니다")
    return _credential


# auto_error=False: 401 응답을 FastAPI 기본 형식이 아니라 ADR 0012 형식으로 직접 만들기 위함
_basic_scheme = HTTPBasic(auto_error=False)


async def require_service_credential(request: Request) -> None:
    expected = get_service_credential()

    # Depends로 받지 않고 직접 호출한다.
    # HTTPBasic은 base64 디코딩 실패, 구분자 누락 등에서 auto_error와 무관하게 HTTPException을 던지는데,
    # Depends로 받으면 이 함수 이전에 예외가 빠져나가 팀 컨벤션 형식이 아닌 FastAPI 기본 응답({"detail": ...})이 나간다.
    # Spring Security가 BasicAuthenticationFilter의 실패도 AuthenticationEntryPoint로 모으는 것과 같도록, 모든 인증 실패를 한 곳(예외 핸들러)으로 모은다.
    try:
        credentials = await _basic_scheme(request)
    except HTTPException as exc:
        raise AuthenticationRequiredError from exc

    if credentials is None:
        raise AuthenticationRequiredError

    # 타이밍 공격 방어: 두 비교를 모두 수행한 뒤에 판정한다 (단축 평가로 건너뛰지 않음)
    username_matches = secrets.compare_digest(
        credentials.username.encode("utf-8"), expected.username.encode("utf-8")
    )
    password_matches = secrets.compare_digest(
        credentials.password.encode("utf-8"), expected.password.encode("utf-8")
    )

    if not (username_matches and password_matches):
        raise AuthenticationRequiredError
