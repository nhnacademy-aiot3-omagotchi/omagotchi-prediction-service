"""
예측 요청 DTO
learning-service와의 계약
"""

from pydantic import Field, model_validator

from app.config import MAX_STUDY_H
from app.schemas.common import CamelModel


class PredictionRequest(CamelModel):
    # learning-service가 가공해서 보내는 피처 32개

    # 공부량 — 타이머 물리 상한(config.MAX_STUDY_H)
    study_lag1: float = Field(ge=0, le=MAX_STUDY_H)
    study_lag2: float = Field(ge=0, le=MAX_STUDY_H)
    study_lag3: float = Field(ge=0, le=MAX_STUDY_H)
    study_7d_mean: float = Field(ge=0, le=MAX_STUDY_H)
    study_30d_mean: float = Field(ge=0, le=MAX_STUDY_H)
    study_all_mean: float = Field(ge=0, le=MAX_STUDY_H)
    study_7d_std: float = Field(ge=0, le=MAX_STUDY_H)

    # 추세 — 공부시간 값들의 차이이므로 같은 범위에 종속
    trend_7_30: float = Field(
        ge=-MAX_STUDY_H, le=MAX_STUDY_H, alias="trend7To30"
    )  # 자동 생성하면 trend730이 되어 7과 30의 경계가 사라진다
    study_diff_1d: float = Field(ge=-MAX_STUDY_H, le=MAX_STUDY_H)

    # 등원 — 비율은 [0,1], 카운트는 7일 창이므로 [0,7]
    att_7d: float = Field(ge=0, le=1)
    att_30d: float = Field(ge=0, le=1)
    att_all: float = Field(ge=0, le=1)
    attend_days_7d: float = Field(ge=0, le=7)

    # 이름과 달리 '오늘(d일)' 미등원 여부임
    # 출석과 타이머 사용은 서로 별개의 흐름이라 study_lag1(오늘 공부시간)과의 정합성은 보장되지 않는다
    noshow_yesterday: int = Field(ge=0, le=1)

    # 태그 (late_7d는 평일 등원 기록이 없으면 null)
    late_7d: float | None = Field(ge=0, le=1)  # 최근 7일 지각률(평일 등원 기록이 아예 없으면 null)
    late_30d: float = Field(ge=0, le=1)
    late_all: float = Field(ge=0, le=1)
    forgot_7d: float = Field(ge=0, le=7)

    # 시간대 — common.py의 ENTRY_CAP: 입실 07:00(420분)~13:50(830분)
    # (미등원일이면 null)
    entry_lag1_min: float | None = Field(ge=420, le=830)  # 오늘 입실 시각(분)(오늘 미등원이면 null)
    entry_7d_mean_min: float | None = Field(ge=420, le=830)  # 최근 7일 평균 입실 시각(최근 7일간 등원 기록이 없으면 null)

    # 게임 — 레벨 상한은 팀 스펙(REQ-LEVEL-04)의 만렙 30을 따름
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

        # tomorrow_dow_5(토)·tomorrow_dow_6(일) 중 하나라도 1이면 내일은 주말 -> is_weekday=0
        # 그 외(월~금)면 is_weekday=1
        expected_weekday = 0 if (self.tomorrow_dow_5 or self.tomorrow_dow_6) else 1
        if self.tomorrow_is_weekday != expected_weekday:
            raise ValueError(
                "tomorrow_is_weekday가 tomorrow_dow_1~6과 모순됩니다"
                f" (dow로 계산한 값={expected_weekday}, 받은 값={self.tomorrow_is_weekday})"
            )
        return self
