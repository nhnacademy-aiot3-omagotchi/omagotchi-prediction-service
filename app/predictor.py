"""
모델 로딩과 예측
Spring과 대응시키면 @Service
"""

import joblib
import pandas as pd
import logging

from app.config import MAX_STUDY_H

from pathlib import Path

from app.schemas import PredictionRequest

logger = logging.getLogger(__name__)


class StudyTimePredictor:
    # 학습된 모델을 감싸고 입력 정렬, 결측 플래그, 범위 보정을 책임진다

    def __init__(self, model_path: str | Path):
        pack = joblib.load(model_path)
        self._model = pack["model"]
        self._features = pack["FEATURES"]  # 35개, 순서 포함
        self._nan_cols = pack["nan_cols"]  # _missing 플래그를 붙일 3개
        self.version = pack["version"]

        self._check_features_match_schema()

    def _check_features_match_schema(self):
        # 모델이 기대하는 피처 목록(joblib 파일 안에 저장된 35개)
        # 모델이 학습될 때 사용한 컬럼 이름 35개를 set으로 만듬 (순서 상관없이 그냥 뭐가 들었는지)
        model_features = set(self._features)

        # 스키마(PredictionRequest)가 실제로 갖고 있는 필드 이름 32개
        # PredictionRequest.model_fields.keys(): Pydantic이 PredictionRequest 클래스를 보고 자동으로 만들어주는 DTO 필드 이름 목록
        schema_fields = set(PredictionRequest.model_fields.keys())

        # 결측 플래그(_missing)도 모델 입장에서는 피처 중 하나이므로 따로 만들어줌
        # late_7d_missing 같은 결측 플래그는 스키마 자체엔 없는 컬럼이라, 따로 더해줌
        missing_flag_fields = set()
        for col in self._nan_cols:
            missing_flag_fields.add(col + "_missing")

        # 실제로 모델에 넘겨줄 수 있는 전체 컬럼 = 스키마 필드 + 결측 플래그
        # 합집합
        expected_features = schema_fields.union(missing_flag_fields)

        # 모델이 기대하는 것과 넘겨줄 수 있는 것이 정확히 같아야 함
        # 우리가 줄 수 있는 것과 모델이 원하는 것이 다르면 ValueError 던져서 __init__ 자체를 실패시킴
        # -> load_predictor() -> lifespan으로 그대로 전파돼서 '모델 문제면 서버 안 뜸'
        if expected_features != model_features:
            # 스키마에만 있는 것
            missing_in_model = expected_features - model_features

            # 모델에만 있는 것
            extra_in_model = model_features - expected_features

            raise ValueError(
                "모델이 기대하는 피처와 스키마가 일치하지 않습니다. "
                f"스키마에는 있는데 모델에는 없는 것: {missing_in_model}, "
                f"모델에는 있는데 스키마에는 없는 것: {extra_in_model}"
            )

    @property
    def feature_count(self) -> int:
        return len(self._features)

    def predict(self, features: dict) -> float:
        row = dict(features)

        # 결측 플래그 파생
        for col in self._nan_cols:
            row[col + "_missing"] = int(row[col] is None)

        # 컬럼 순서를 모델 기준으로 강제
        X = pd.DataFrame([row])[self._features].astype(float)  # None -> NaN, float64
        y_hat = float(self._model.predict(X)[0])

        clamped = min(max(y_hat, 0.0), MAX_STUDY_H)

        if clamped != y_hat:
            logger.warning("예측값 보정: raw = %.4f -> clamped = %.4f", y_hat, clamped)

        # 응답 스펙 보장: 공부시간은 [0, 11.5] 안에 있다
        return clamped


_predictor: StudyTimePredictor | None = None


def load_predictor(model_path: str | Path) -> None:
    # 앱 기동 시 1회 호출
    global _predictor
    _predictor = StudyTimePredictor(model_path)


def get_predictor() -> StudyTimePredictor:
    # FastAPI 의존성 주입용 (Spring의 @Autowired 같은 것)
    if _predictor is None:
        raise RuntimeError("predictor가 로드되지 않았습니다")
    return _predictor
