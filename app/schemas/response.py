"""
예측 응답 DTO
"""

from app.schemas.common import CamelModel


class PredictionResponse(CamelModel):
    predicted_study_hours: float
    model_version: str
