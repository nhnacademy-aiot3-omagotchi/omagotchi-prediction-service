"""
예상 가능한 4xx: 스택 트레이스 남기지 X
예상치 못한 5xx: 원본 예외(스택 트레이스)를 로그에 보존
-> 잠가두는 테스트

client, api_payload, broken_predictor_installed fixture는 conftest.py에 있음
"""

import logging
import app.predictor as predictor_module


def test_validation_failure_does_not_log_stack_trace(client, caplog):
    with caplog.at_level(logging.WARNING, logger="app.main"):
        client.post("/api/v1/predictions/study-time", json={"studyLag1": 5.0})

    records = [r for r in caplog.records if r.name == "app.main"]

    assert len(records) == 1
    assert records[0].levelname == "WARNING"
    assert records[0].exc_info is None


def test_unhandle_exception_logs_stack_trace(
    client, api_payload, broken_predictor_installed, caplog
):
    with caplog.at_level(logging.WARNING, logger="app.main"):
        client.post("/api/v1/predictions/study-time", json=api_payload)

    records = [r for r in caplog.records if r.name == "app.main"]

    assert len(records) == 1
    assert records[0].levelname == "ERROR"
    assert records[0].exc_info is not None
    assert "RuntimeError" in caplog.text


def test_model_not_loaded_logs_warning_without_stack_trace(
    client, api_payload, monkeypatch, caplog
):
    monkeypatch.setattr(predictor_module, "_predictor", None)

    with caplog.at_level(logging.WARNING, logger="app.main"):
        client.post("/api/v1/predictions/study-time", json=api_payload)

    records = [r for r in caplog.records if r.name == "app.main"]

    assert len(records) == 1
    assert records[0].levelname == "WARNING"
    assert records[0].exc_info is None
