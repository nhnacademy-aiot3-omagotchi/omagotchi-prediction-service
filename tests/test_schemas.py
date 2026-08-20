"""
PredictionRequest 검증 규칙 테스트
"""

import math

import pytest
from pydantic import ValidationError

from app.schemas import PredictionRequest


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
