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
# 실제 타이머는 입퇴실과 무관하게 기록되어 이론상 이보다 더 클 수 있지만, 모델은 이 범위를 넘는 입력을 학습해 본 적이 없어 신뢰할 수 있는 예측을 보장하지 못한다
# 그래서 요청 필드가 이 범위를 넘으면 보정하지 않고 400으로 거부한다
# 값을 이 범위 안으로 맞추는 것(클램프)은 learning-service의 책임
# 퀘스트 가중치, 상하한 같은 정책도 learning-service가 소유
MAX_STUDY_H = 11.5
