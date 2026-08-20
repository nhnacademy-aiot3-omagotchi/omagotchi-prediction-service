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


def error_body(error_code: ErrorCode, path: str, request_id: str | None = None) -> dict:
    # requestId는 전파 구현 전까지는 널 허용 TODO 나중에 고칠 것!
    return {
        "code": error_code.code,
        "message": error_code.message,
        "path": path,
        "requestId": request_id,
    }
