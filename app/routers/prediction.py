"""
예측 엔드포인트
Spring과 대응시키면 @RestController
"""

from fastapi import APIRouter, Depends

from app.predictor import StudyTimePredictor, get_predictor
from app.schemas import PredictionRequest, PredictionResponse

router = APIRouter(prefix="/api/v1/predictions", tags=["predictions"])


@router.post("/study-time", response_model=PredictionResponse)
def predict_study_time(
    request: PredictionRequest,
    predictor: StudyTimePredictor = Depends(get_predictor),
) -> PredictionResponse:
    y_hat = predictor.predict(request.model_dump())
    return PredictionResponse(
        predicted_study_hours=round(y_hat, 3), model_version=predictor.version
    )
