"""
요청/응답 DTO
Spring과 대응시키면 DTO(Request/Response) 패키지

app.schemas.PredictionRequest/PredictionResponse로 계속 import 할 수 있도록 재노출
"""

from app.schemas.common import CamelModel, to_camel_api
from app.schemas.request import PredictionRequest
from app.schemas.response import PredictionResponse

__all__ = ["CamelModel", "to_camel_api", "PredictionRequest", "PredictionResponse"]
