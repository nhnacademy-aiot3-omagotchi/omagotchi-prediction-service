"""
모델 로딩과 예측
Spring과 대응시키면 @Service
"""

import joblib
import pandas as pd

from app.config import MAX_STUDY_H


class StudyTimePredictor:
    # 학습된 모델을 감싸고 입력 정렬, 결측 플래그, 범위 보정을 책임진다

    def __init__(self, model_path: str):
        pack = joblib.load(model_path)
        self._model = pack["model"]
        self._features = pack["FEATURES"]  # 35개, 순서 포함
        self._nan_cols = pack["nan_cols"]  # _missing 플래그를 붙일 3개
        self.version = pack["version"]

    def predict(self, features: dict) -> float:
        row = dict(features)

        # 결측 플래그 파생
        for col in self._nan_cols:
            row[col + "_missing"] = int(row[col] is None)

        # 컬럼 순서를 모델 기준으로 강제
        X = pd.DataFrame([row])[self._features].astype(float)  # None -> NaN, float64
        y_hat = float(self._model.predict(X)[0])

        # 응답 스펙 보장: 공부시간은 [0, 11.5] 안에 있다
        return min(max(y_hat, 0.0), MAX_STUDY_H)


_predictor: StudyTimePredictor | None = None


def load_predictor(model_path: str) -> None:
    # 앱 기동 시 1회 호출
    global _predictor
    _predictor = StudyTimePredictor(model_path)


def get_predictor() -> StudyTimePredictor:
    # FastAPI 의존성 주입용 (Spring의 @Autowired 같은 것)
    if _predictor is None:
        raise RuntimeError("predictor가 로드되지 않았습니다")
    return _predictor
