"""
요청/응답 DTO
learning-service와의 계약
Spring과 대응시키면 DTO(Request/Response)
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import math


def to_camel_api(snake: str) -> str:
    """
    nake_case -> camelCase
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


class PredictionRequest(CamelModel):
    # learning-service가 가공해서 보내는 피처 32개

    # 공부량 — 타이머 물리 상한(MAX_STUDY_H = 11.5h)
    study_lag1: float = Field(ge=0, le=11.5)
    study_lag2: float = Field(ge=0, le=11.5)
    study_lag3: float = Field(ge=0, le=11.5)
    study_7d_mean: float = Field(ge=0, le=11.5)
    study_30d_mean: float = Field(ge=0, le=11.5)
    study_all_mean: float = Field(ge=0, le=11.5)
    study_7d_std: float = Field(ge=0, le=11.5)

    # 추세 — 공부시간 값들의 차이이므로 같은 범위에 종속
    trend_7_30: float = Field(
        ge=-11.5, le=11.5, alias="trend7To30"
    )  # 자동 생성하면 trend730이 되어 7과 30의 경계가 사라진다
    study_diff_1d: float = Field(ge=-11.5, le=11.5)

    # 등원 — 비율은 [0,1], 카운트는 7일 창이므로 [0,7]
    att_7d: float = Field(ge=0, le=1)
    att_30d: float = Field(ge=0, le=1)
    att_all: float = Field(ge=0, le=1)
    attend_days_7d: float = Field(ge=0, le=7)
    noshow_yesterday: int = Field(ge=0, le=1)

    # 태그 (late_7d는 평일 등원 기록이 없으면 null)
    late_7d: float | None = Field(default=None, ge=0, le=1)
    late_30d: float = Field(ge=0, le=1)
    late_all: float = Field(ge=0, le=1)
    forgot_7d: float = Field(ge=0, le=7)

    # 시간대 — common.py의 ENTRY_CAP: 입실 07:00(420분)~13:50(830분)
    # (미등원일이면 null)
    entry_lag1_min: float | None = Field(default=None, ge=420, le=830)
    entry_7d_mean_min: float | None = Field(default=None, ge=420, le=830)

    # 게임 — level은 data/generate.py의 MAX_LEVEL=30.
    # quests_total·quest_streak는 시간이 지나며 계속 느는 누적값이라 상한을 두지 않는다.
    level: int = Field(ge=1, le=30)
    quests_total: int = Field(ge=0)
    quest_streak: int = Field(ge=0)
    quest_rate_7d: float = Field(ge=0, le=1)

    # 달력 (내일 기준) — 원-핫이므로 각 플래그는 0/1
    tomorrow_is_weekday: int = Field(ge=0, le=1)
    tomorrow_dow_1: int = Field(ge=0, le=1)
    tomorrow_dow_2: int = Field(ge=0, le=1)
    tomorrow_dow_3: int = Field(ge=0, le=1)
    tomorrow_dow_4: int = Field(ge=0, le=1)
    tomorrow_dow_5: int = Field(ge=0, le=1)
    tomorrow_dow_6: int = Field(ge=0, le=1)
    # 첫 기록일로부터 지난 일수 — 계속 느는 값이라 상한 없음
    days_since_start: int = Field(ge=0)

    @model_validator(mode="after")
    def check_dow_onehot(self) -> "PredictionRequest":
        # 원-핫이므로 화요일 ~ 일요일 중 최대 하나만 1이어야 한다 (전부 0이면 월요일)
        dows = [
            self.tomorrow_dow_1,
            self.tomorrow_dow_2,
            self.tomorrow_dow_3,
            self.tomorrow_dow_4,
            self.tomorrow_dow_5,
            self.tomorrow_dow_6,
        ]
        if sum(dows) > 1:
            raise ValueError("tomorrow_dow_1~6 중 하나만 1이어야 합니다 (원-핫)")
        return self


class PredictionResponse(CamelModel):
    predicted_study_hours: float
    model_version: str
