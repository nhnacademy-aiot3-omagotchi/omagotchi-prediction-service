"""
공통 테스트 fixture
Java로 치면 공유 테스트 지원 클래스나 static 상수 파일에 둘 것들
여기 두면 import 없이 모든 테스트 파일에 자동으로 주입됨
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.predictor import get_predictor
from app.schemas import PredictionRequest


@pytest.fixture
def client():

    # raise_server_exceptions=False: 500도 응답으로 받아서 검사하기 위해 켰음
    # (기본값 True면 ServerErrorMiddleware가 재발생시키는 예외가 테스트를 실패시킴)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    app.dependency_overrides.clear()  # 다음 테스트로 새지 않게 정리


@pytest.fixture
def valid_payload() -> dict:
    # HTTP 요청 본문 그대로 (snake_case)
    # 실제 features.parquet에서 뽑은 유효한 요청 (2026-06-26 / user9 기준)
    return {
        "study_lag1": 9.5978,  # 오늘 공부량 (예측 당시의 어제)
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


@pytest.fixture
def api_payload(valid_payload) -> dict:
    # HTTP 요청 본문 그대로 (camelCase)
    # 실제 features.parquet에서 뽑은 유효한 요청 (2026-06-26 / user9 기준)
    return PredictionRequest(**valid_payload).model_dump(by_alias=True)


@pytest.fixture
def broken_predictor_installed():
    # predictor.predict()가 항상 RuntimeError를 내도록 주입 (500 유발용)
    # 가짜 predictor
    def broken_predictor():
        class Broken:
            version = "broken"

            def predict(self, features):
                raise RuntimeError("테스트용 강제 예외")

        return Broken()

    app.dependency_overrides[get_predictor] = broken_predictor
