"""
예측 엔드포인트
Spring과 대응시키면 @RestController
"""

import logging
import time

from fastapi import APIRouter, Depends, Request

from app.config import MAX_STUDY_H
from app.predictor import StudyTimePredictor, get_predictor
from app.request_id import get_request_id
from app.schemas import PredictionRequest, PredictionResponse
from app.security import require_service_credential

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/predictions",
    tags=["predictions"],
    # 라우터 전체에 적용 — 이후 추가되는 엔드포인트도 자동으로 인증 대상이 된다
    dependencies=[Depends(require_service_credential)],
)


@router.post("/study-time", response_model=PredictionResponse)
def predict_study_time(
        payload: PredictionRequest,
        request: Request,
        predictor: StudyTimePredictor = Depends(get_predictor),
) -> PredictionResponse:
    started_at = time.perf_counter()
    calculation = predictor.predict(payload.model_dump())
    inference_elapsed_ms = (time.perf_counter() - started_at) * 1000
    response_hours = round(calculation.clamped_hours, 3)

    adjustment = _adjustment_description(calculation.raw_hours)
    log_method = (
        logger.warning
        if calculation.raw_hours != calculation.clamped_hours
        else logger.info
    )
    log_method(
        "학습 시간 예측 완료: "
        "원본예측(rawPredictedStudyHours)=%.4f시간 "
        "→ 출력범위보정(adjustment)=%s "
        "→ 응답반올림(responsePredictedStudyHours)=%.3f시간 "
        "| 내일요일(tomorrowDayOfWeek)=%s, "
        "평일여부(tomorrowIsWeekday)=%s, "
        "모델(modelVersion)=%s, 추론시간(inferenceElapsedMs)=%.1fms, "
        "요청ID(requestId)=%s",
        calculation.raw_hours,
        adjustment,
        response_hours,
        _tomorrow_day_of_week(payload),
        "예(1)" if payload.tomorrow_is_weekday else "아니오(0)",
        predictor.version,
        inference_elapsed_ms,
        get_request_id(request),
    )

    return PredictionResponse(
        predicted_study_hours=response_hours, model_version=predictor.version
    )


def _adjustment_description(raw_hours: float) -> str:
    if raw_hours < 0.0:
        return "최소 0시간 적용(MIN_CLAMP)"
    if raw_hours > MAX_STUDY_H:
        return f"최대 {MAX_STUDY_H:g}시간 적용(MAX_CLAMP)"
    return "보정 없음(NONE)"


def _tomorrow_day_of_week(payload: PredictionRequest) -> str:
    days = (
        "월요일(MONDAY)",
        "화요일(TUESDAY)",
        "수요일(WEDNESDAY)",
        "목요일(THURSDAY)",
        "금요일(FRIDAY)",
        "토요일(SATURDAY)",
        "일요일(SUNDAY)",
    )
    day_flags = (
        payload.tomorrow_dow_1,
        payload.tomorrow_dow_2,
        payload.tomorrow_dow_3,
        payload.tomorrow_dow_4,
        payload.tomorrow_dow_5,
        payload.tomorrow_dow_6,
    )
    selected = next((index for index, value in enumerate(day_flags, 1) if value), 0)
    return days[selected]
