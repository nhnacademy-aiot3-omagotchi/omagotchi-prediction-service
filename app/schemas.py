"""
요청/응답 DTO
learning-service와의 계약
Spring과 대응시키면 DTO(Request/Response)
"""

from pydantic import BaseModel, ConfigDict, Field


def to_camel_api(snake: str) -> str:
    """
    nake_case -> camelCase
    숫자로 시작하는 조각은 대문자화하지 않는다
    pydantic 기본 to_camel은 study_7d_mean을 study7DMean으로 만드는데,
    Java 관례상 study7dMean이 자연스럽다
    """
    head, *rest = snake.split("_")
    return head + "".join(w if w[0].isdigit() else w.capitalize() for w in rest)


class CamelModel(BaseModel):
    # JSON은 camelCase(Java 관례), Python 내부는 snake_case
    model_config = ConfigDict(alias_generator=to_camel_api, populate_by_name=True)


class PredictionRequest(CamelModel):
    # learning-service가 가공해서 보내는 피처 32개

    # 공부량
    study_lag1: float
    study_lag2: float
    study_lag3: float
    study_7d_mean: float
    study_30d_mean: float
    study_all_mean: float
    study_7d_std: float

    # 추세
    trend_7_30: float = Field(
        alias="trend7To30"
    )  # 자동 생성하면 trend730이 되어 7과 30의 경계가 사라진다
    study_diff_1d: float

    # 등원
    att_7d: float
    att_30d: float
    att_all: float
    attend_days_7d: float
    noshow_yesterday: int

    # 태그 (late_7d는 평일 등원 기록이 없으면 null)
    late_7d: float | None = None
    late_30d: float
    late_all: float
    forgot_7d: float

    # 시간대 (미등원일이면 null)
    entry_lag1_min: float | None = None
    entry_7d_mean_min: float | None = None

    # 게임
    level: int
    quests_total: int
    quest_streak: int
    quest_rate_7d: float

    # 달력 (내일 기준)
    tomorrow_is_weekday: int
    tomorrow_dow_1: int
    tomorrow_dow_2: int
    tomorrow_dow_3: int
    tomorrow_dow_4: int
    tomorrow_dow_5: int
    tomorrow_dow_6: int
    days_since_start: int


class PredictionResponse(CamelModel):
    predicted_study_hours: float
    model_version: str
