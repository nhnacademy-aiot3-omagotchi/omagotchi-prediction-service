"""
서비스 설정값
Spring과 대응시키면 application.yml과 같은 것
"""

MODEL_PATH = "models/study_time_model.joblib"

# 타이머 물리 상한 - 학습 데이터의 영역이지, 서비스 정책이 아니다
# 퀘스트 가중치, 상하한 같은 정책은 learning-service가 소유한다
MAX_STUDY_H = 11.5
