"""
서비스 설정값
Spring과 대응시키면 application.yml과 같은 것
"""

from pathlib import Path

# 이 파일(app/config.py)의 두 단계 위 = 프로젝트 루트
# 실행 위치(cwd)와 무관하게 모델을 찾기 위함
BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_PATH = BASE_DIR / "models" / "study_time_model.joblib"

# 예측 AI를 만들 때 정한 모델 입력·출력 경계이며 타이머의 도메인 상한이 아니다
# learning-service는 계산한 공부시간 피처를 이 상한으로 보정해 전달한다
# 퀘스트 가중치, 상하한 같은 정책은 learning-service가 소유한다
MAX_STUDY_H = 11.5
