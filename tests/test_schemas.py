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


# null이 유효한 값인 것과, 키를 생략해도 되는 것은 별개 문제임
@pytest.mark.parametrize("field", ["late_7d", "entry_lag1_min", "entry_7d_mean_min"])
def test_nullable_field_omission_rejected(valid_payload, field):
    # nullable이어도 키 자체를 생략하는 건 허용되지 않는다 (명시적 null만 허용)
    del valid_payload[field]
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


def test_valid_monday_case_accepted(valid_payload):
    # 요일 전부 0 = 월요일, is_weekday=1 이어야 정상
    for i in range(1, 7):
        valid_payload[f"tomorrow_dow_{i}"] = 0
    valid_payload["tomorrow_is_weekday"] = 1
    req = PredictionRequest(**valid_payload)
    assert req.tomorrow_is_weekday == 1


def test_attended_with_zero_study_time_accepted(valid_payload):
    # noshow_yesterday는 전날 출결이고 study_lag1은 기준일 공부시간이므로 조합 제약을 두지 않는다
    valid_payload["noshow_yesterday"] = 0
    valid_payload["study_lag1"] = 0.0
    req = PredictionRequest(**valid_payload)

    assert req.study_lag1 == 0.0
