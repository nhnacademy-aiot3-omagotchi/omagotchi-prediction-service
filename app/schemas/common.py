"""
DTO 공용 베이스
learning-service와의 계약에서 camelCase 변환, 공통 검증 담당
"""

import math

from pydantic import BaseModel, ConfigDict, field_validator


def to_camel_api(snake: str) -> str:
    """
    snake_case -> camelCase
    숫자로 시작하는 조각은 대문자화하지 않는다
    pydantic 기본 to_camel은 study_7d_mean을 study7DMean으로 만드는데, Java 관례상 study7dMean이 자연스럽다
    """
    head, *rest = snake.split("_")
    return head + "".join(w if w[0].isdigit() else w.capitalize() for w in rest)


class CamelModel(BaseModel):
    # JSON은 camelCase(Java 관례), Python 내부는 snake_case
    model_config = ConfigDict(
        alias_generator=to_camel_api, populate_by_name=True, extra="forbid"
    )

    @field_validator("*", mode="before")
    @classmethod
    def reject_non_finite(cls, v):
        # NaN, Infinity는 ge/le 범위 비교를 그냥 통과해버리므로 별도로 막는다
        # (NaN >= 0, NaN <= 11.5 등은 전부 False라 Field 제약만으로는 못 잡음)
        if isinstance(v, float) and not math.isfinite(v):
            raise ValueError("NaN 또는 Infinity는 허용되지 않습니다")
        return v
