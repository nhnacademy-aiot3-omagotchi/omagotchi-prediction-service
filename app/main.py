"""
애플리케이션 진입점
Spring과 대응시키면 Application.java
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import MODEL_PATH
from app.predictor import get_predictor, is_loaded, load_predictor
from app.routers import prediction


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 기동 시 모델을 한 번만 로드한다 (Spring의 @PostConstruct 같은 것)
    load_predictor(MODEL_PATH)
    yield


app = FastAPI(
    title="Omagotchi Study-Time Prediction",
    description="learning-service가 보낸 피쳐로 내일 공부 시간을 예측한다",
    lifespan=lifespan,
)

app.include_router(prediction.router)


@app.get("/health", tags=["health"])
def health():
    if not is_loaded():
        # 503 = Service Unavailable
        # Gateway, Eureka가 상태코드로 판단한다
        return JSONResponse(status_code=503, content={"status": "DOWN"})

    return {"status": "UP", "modelVersion": get_predictor().version}
