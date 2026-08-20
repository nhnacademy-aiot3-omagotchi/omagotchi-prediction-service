"""
PredictionRequest 검증 규칙 테스트
"""

import math

import pytest
from pydantic import ValidationError

from app.schemas import PredictionRequest


@pytest.fixture
def valid_payload() -> dict:
    """실제 features.parquet에서 뽑은 유효한 요청 (2026-06-26 / user9 기준)."""
    return {
        "study_lag1": 9.5978,
        "study_lag2": 9.6236,
        "study_lag3": 8.1269,
        "study_7d_mean": 7.3602,
        "study_30d_mean": 6.9199,
        "study_all_mean": 6.7323,
        "study_7d_std": 3.5685,
        "trend_7_30": 0.4403,
        "study_diff_1d": -0.0258,
        "att_7d": 1.0,
        "att_30d": 0.9545,
        "att_all": 0.9767,
        "attend_days_7d": 6.0,
        "noshow_yesterday": 0,
        "late_7d": 0.0,
        "late_30d": 0.0,
        "late_all": 0.0238,
        "forgot_7d": 0.0,
        "entry_lag1_min": 540.0,
        "entry_7d_mean_min": 539.1667,
        "level": 18,
        "quests_total": 142,
        "quest_streak": 2,
        "quest_rate_7d": 0.5714,
        "tomorrow_is_weekday": 0,
        "tomorrow_dow_1": 0,
        "tomorrow_dow_2": 0,
        "tomorrow_dow_3": 0,
        "tomorrow_dow_4": 0,
        "tomorrow_dow_5": 1,
        "tomorrow_dow_6": 0,
        "days_since_start": 298,
    }


def test_valid_payload_accepted(valid_payload):
    req = PredictionRequest(**valid_payload)
    assert req.study_lag1 == 9.5978


def test_range_violation_rejected(valid_payload):
    valid_payload["study_lag1"] = 9999.0
    with pytest.raises(ValidationError):
        PredictionRequest(**valid_payload)


def test_ratio_out_of_range_rejected(valid_payload):
    valid_payload["att_7d"] = 88.0
    with pytest.raises(ValidationError):
        PredictionRequest(**valid_payload)


@pytest.mark.parametrize("field", ["late_7d", "entry_lag1_min", "entry_7d_mean_min"])
def test_nullable_fields_accept_none(valid_payload, field):
    valid_payload[field] = None
    req = PredictionRequest(**valid_payload)
    assert getattr(req, field) is None


@pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf])
def test_non_finite_values_rejected(valid_payload, bad_value):
    valid_payload["study_lag1"] = bad_value
    with pytest.raises(ValidationError):
        PredictionRequest(**valid_payload)


def test_unknown_field_rejected(valid_payload):
    valid_payload["studyLagg1"] = 5.0  # 오타 필드
    with pytest.raises(ValidationError):
        PredictionRequest(**valid_payload)


def test_missing_field_rejected(valid_payload):
    del valid_payload["study_lag2"]
    with pytest.raises(ValidationError):
        PredictionRequest(**valid_payload)


def test_dow_onehot_violation_rejected(valid_payload):
    valid_payload["tomorrow_dow_1"] = 1  # dow_5도 이미 1이라 두 개가 1이 됨
    with pytest.raises(ValidationError):
        PredictionRequest(**valid_payload)


def test_weekday_dow_mismatch_rejected(valid_payload):
    # dow_5(토)=1인데 is_weekday=1이라고 우김 -> 모순
    valid_payload["tomorrow_is_weekday"] = 1
    with pytest.raises(ValidationError):
        PredictionRequest(**valid_payload)


def test_noshow_with_positive_study_time_rejected(valid_payload):
    valid_payload["noshow_yesterday"] = 1  # 미등원인데
    valid_payload["study_lag1"] = 9.5  # 공부시간이 있음 -> 모순
    with pytest.raises(ValidationError):
        PredictionRequest(**valid_payload)


def test_attended_with_zero_study_time_rejected(valid_payload):
    valid_payload["noshow_yesterday"] = 0  # 등원인데
    valid_payload["study_lag1"] = 0.0  # 공부시간이 0 -> 모순
    with pytest.raises(ValidationError):
        PredictionRequest(**valid_payload)


def test_valid_monday_case_accepted(valid_payload):
    # 요일 전부 0 = 월요일, is_weekday=1 이어야 정상
    for i in range(1, 7):
        valid_payload[f"tomorrow_dow_{i}"] = 0
    valid_payload["tomorrow_is_weekday"] = 1
    req = PredictionRequest(**valid_payload)
    assert req.tomorrow_is_weekday == 1
