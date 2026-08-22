"""
StudyTimePredictor 단위 테스트

monkeypatch는 pytest 내장 fixture로 Mockito의 when...thenReturn... 같은 것임
caplog도 pytest 내장으로, 로그가 실제로 찍혔는지 안 찍혔는지 검증할 때 사용함
"""

import app.predictor as predictor_module
import logging

import joblib
import numpy as np
import pytest

from app.config import MAX_STUDY_H, MODEL_PATH
from app.predictor import StudyTimePredictor


@pytest.fixture
def predictor() -> StudyTimePredictor:
    return StudyTimePredictor(MODEL_PATH)


@pytest.fixture
def base_features(predictor) -> dict:
    # 결측 없는 입력
    # 클램프 로직만 검증하므로 실제 값 의미는 중요 X
    return {f: 1.0 for f in predictor._features if not f.endswith("_missing")}


def test_normal_prediction_within_range(predictor, base_features):
    y_hat = predictor.predict(base_features)

    assert 0.0 <= y_hat <= MAX_STUDY_H


def test_negative_model_output_clamped_to_zero(predictor, base_features, monkeypatch):
    monkeypatch.setattr(predictor._model, "predict", lambda X: np.array([-0.566]))

    assert predictor.predict(base_features) == 0.0


def test_excessive_model_output_clamped_to_max(predictor, base_features, monkeypatch):
    monkeypatch.setattr(predictor._model, "predict", lambda X: np.array([15.0]))

    assert predictor.predict(base_features) == MAX_STUDY_H


def test_clamp_logs_warning(predictor, base_features, monkeypatch, caplog):
    monkeypatch.setattr(predictor._model, "predict", lambda X: np.array([-0.566]))
    with caplog.at_level(logging.WARNING, logger="app.predictor"):
        predictor.predict(base_features)

    assert any("보정" in record.message for record in caplog.records)


def test_no_clamp_no_warning_logged(predictor, base_features, monkeypatch, caplog):
    monkeypatch.setattr(predictor._model, "predict", lambda X: np.array([5.0]))
    with caplog.at_level(logging.WARNING, logger="app.predictor"):
        predictor.predict(base_features)

    assert len(caplog.records) == 0


def test_missing_value_handled(predictor, base_features):
    # 결측(None)이 섞여도 죽지 않고 정상 범위 내 값이 나와야 한다
    base_features["entry_lag1_min"] = None
    y_hat = predictor.predict(base_features)

    assert 0.0 <= y_hat <= MAX_STUDY_H


# get_predictor()의 RuntimeError (도달하기 어렵기는 함)
def test_get_predictor_raises_when_not_loaded(monkeypatch):
    monkeypatch.setattr(predictor_module, "_predictor", None)

    with pytest.raises(RuntimeError):
        predictor_module.get_predictor()


# monkeypatch는 pytest가 기본으로 제공하는 fixture (Mockito의 when().thenReturn()처럼 테스트 끝나면 자동으로 원상복구되는 가짜 교체 도구임)
def test_feature_schema_mismatch_rejected(monkeypatch):

    # 진짜 모델 파일을 그대로 한 번 읽어옴
    # joblib.load()는 파이썬 객체를 파일로 저장/복원하는 라이브러리임
    # 이 파일 안엔 {"model": ..., "FEATURES": [...35개...], "nan_cols": [...], "version": "..."} 형태의 dict가 들어있음
    real_pack = joblib.load(MODEL_PATH)

    # 그 dict를 복사한 다음, FEATURES 리스트에서 마지막 항목만 하나 빼버림
    broken_pack = dict(real_pack)
    broken_pack["FEATURES"] = real_pack["FEATURES"][
        :-1
    ]  # 피처 하나 슬라이싱해서 몰래 제거

    # joblib.load 함수 자체를 무슨 경로로 넘겨받든 무조건 broken_pack(가짜 데이터)을 돌려주는 함수로 바꿔치기 (Mockito같은)
    monkeypatch.setattr(joblib, "load", lambda path: broken_pack)

    # 생성 (가짜 경로를 넘기지만 joblib.load가 이미 가짜라서 파일을 진짜 찾으러 가지 않고 바로 broken_pack을 돌려줌)
    # 그러면 __init__ 안에서 self._check_features_match_schema()가 실행되면서 스키마는 35개를 기대하는데 모델은 34개를 줬다는 것을 알고 ValueError 던짐
    # pytest.raises(ValueError) -> 이 블락 안에서 이 예외가 터져야 테스트 성공
    with pytest.raises(ValueError):
        StudyTimePredictor("dummy-path")
