"""
StudyTimePredictor 단위 테스트

monkeypatch는 pytest 내장 fixture로 Mockito의 when...thenReturn... 같은 것임
caplog도 pytest 내장으로, 로그가 실제로 찍혔는지 안 찍혔는지 검증할 때 사용함
"""

import app.predictor as predictor_module
import logging

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
