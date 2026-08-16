"""
서비스 설정값
Spring과 대응시키면 application.yml과 같은 것
"""

from pathlib import Path

# 이 파일(app/config.py)의 두 단계 위 = 프로젝트 루트
# 실행 위치(cwd)와 무관하게 모델을 찾기 위함
BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_PATH = BASE_DIR / "models" / "study_time_model.joblib"

# 타이머 물리 상한 - 학습 데이터의 영역이지, 서비스 정책이 아니다
# 퀘스트 가중치, 상하한 같은 정책은 learning-service가 소유한다
MAX_STUDY_H = 11.5
