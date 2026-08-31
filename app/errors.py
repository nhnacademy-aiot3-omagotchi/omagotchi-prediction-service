"""
공통 오류 코드
Spring과 대응시키면 ErrorCode ENUM
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorCode:
    code: str
    message: str
    status: int


COMMON_INVALID_REQUEST = ErrorCode(
    code="COMMON_INVALID_REQUEST",
    message="요청값이 올바르지 않습니다.",
    status=400,
)
COMMON_INTERNAL_SERVER_ERROR = ErrorCode(
    code="COMMON_INTERNAL_SERVER_ERROR",
    message="일시적인 오류가 발생했습니다.",
    status=500,
)
AUTH_AUTHENTICATION_REQUIRED = ErrorCode(
    code="AUTH_AUTHENTICATION_REQUIRED",
    message="인증이 필요합니다.",
    status=401,
)


# RequestIDMiddleware가 모든 HTTP 요청에 항상 값을 채워주지만, 이 함수 자체는 미들웨어 경로 밖에서도 쓸 수 있도록 None 허용
def error_body(error_code: ErrorCode, path: str, request_id: str | None = None) -> dict:
    return {
        "code": error_code.code,
        "message": error_code.message,
        "path": path,
        "requestId": request_id,
    }
