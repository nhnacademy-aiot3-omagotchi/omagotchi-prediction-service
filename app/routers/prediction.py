"""
예측 엔드포인트
Spring과 대응시키면 @RestController
"""

from fastapi import APIRouter, Depends

from app.predictor import StudyTimePredictor, get_predictor
from app.schemas import PredictionRequest, PredictionResponse
from app.security import require_service_credential

router = APIRouter(
    prefix="/api/v1/predictions",
    tags=["predictions"],
    # 라우터 전체에 적용 — 이후 추가되는 엔드포인트도 자동으로 인증 대상이 된다
    dependencies=[Depends(require_service_credential)],
)


@router.post("/study-time", response_model=PredictionResponse)
def predict_study_time(
    request: PredictionRequest,
    predictor: StudyTimePredictor = Depends(get_predictor),
) -> PredictionResponse:
    y_hat = predictor.predict(request.model_dump())
    return PredictionResponse(
        predicted_study_hours=round(y_hat, 3), model_version=predictor.version
    )
