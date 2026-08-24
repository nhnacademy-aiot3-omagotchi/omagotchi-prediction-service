# Omagotchi Prediction Service

내일 예상 공부 시간을 예측하는 ML 추론 전용 서비스입니다. learning-service가 계산해서 보낸 피처 32개를 받아 LightGBM 모델로 `[0, 11.5]`h 범위의 예측값을 반환합니다.

## 역할

- 피처 32개 입력 → 내일 공부 시간 예측 (예측 모델 출력 경계 `MAX_STUDY_H = 11.5`h로 보정)
- 순수 추론만 담당 — 퀘스트 정책(도전 계수, 상하한 클립, 콜드스타트 규칙 폴백)은 전부 learning-service 책임
- 원시 학습 기록을 직접 조회하지 않음 — learning-service가 이미 계산해서 보낸 피처만 사용
- learning-service는 계산한 공부시간 입력 피처를 예측 모델 경계 `11.5`h로 보정해 전달함
- 이 서비스의 비정상 응답은 learning-service가 내부 오류로 로그하고, 조회 API 호출자에게 일반 `500` 응답으로 반환함

역할·책임 경계 근거: [ADR 0001 서비스 분리와 모델 아티팩트](https://github.com/nhnacademy-aiot3-omagotchi/docs/blob/main/30-adr/prediction/0001-service-separation-and-model-artifact.md), [ADR 0002 learning-service 통신 경계](https://github.com/nhnacademy-aiot3-omagotchi/docs/blob/main/30-adr/prediction/0002-learning-service-communication-boundary.md)

## 로컬 실행

- 런타임: Python 3.12
- 필수 리소스: `models/study_time_model.joblib` (학습 산출물, 저장소에 직접 커밋되어 있음)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # 운영 + 테스트 의존성 전부
pytest tests/ -v                       # 36 passed 나와야 정상
uvicorn app.main:app --reload --port 8085
```

- 상태 확인: `GET /health`
- Swagger UI: `/docs` (FastAPI 자동 생성)
- 요청 예시: [`http/prediction.http`](http/prediction.http) 

> **모델 로드 실패 시 애플리케이션 기동 자체가 실패합니다.** 이 서비스의 유일한 기능이 예측이라 모델은 필수 리소스이며, 팀 "시작 실패" 정책(원본 예외 전파 + 기동 중단)을 그대로 따릅니다. 헬스체크로 DOWN을 알리는 게 아니라 프로세스 자체가 뜨지 않으니, 오케스트레이터의 재시작·배포 실패 감지에 의존합니다.

## 디렉터리 구조

```
app/
├── config.py             # 모델 경로(절대경로), 예측 모델 경계 MAX_STUDY_H
├── errors.py             # 공통 오류 코드(ErrorCode), error_body()
├── exception_handlers.py  # 예외 핸들러 2개 (Spring @ControllerAdvice/global.exception 격)
├── main.py               # 앱 조립, lifespan(모델 로드), /health
├── predictor.py           # StudyTimePredictor — 모델 로딩과 예측 (Spring @Service격)
├── request_id.py          # X-Request-ID 전파 미들웨어 (순수 ASGI)
├── routers/
│   └── prediction.py     # POST /api/v1/predictions/study-time
└── schemas/               # PredictionRequest/Response DTO (Spring DTO 패키지 격)
    ├── common.py         # CamelModel, to_camel_api() — camelCase 변환·공통 검증
    ├── request.py         # PredictionRequest — 범위·크로스필드 검증
    └── response.py        # PredictionResponse

tests/
├── conftest.py                  # 공유 fixture
├── test_startup.py              # 애플리케이션 기동 테스트
├── test_schemas.py              # 요청 검증 규칙
├── test_predictor.py            # 예측/클램프 로직 단위 테스트
├── test_api.py                  # HTTP 경계(200/400/500, Request ID)
├── test_request_id_regression.py # Request ID 미들웨어 회귀 테스트
└── test_error_log_policy.py     # 4xx/5xx 로그 레벨·스택트레이스 정책
```

## API 경계

| Method | URI | 설명 | 인증 |
|---|---|---|---|
| POST | `/api/v1/predictions/study-time` | 공부 시간 예측 | 없음 (알려진 갭) |
| GET | `/health` | 상태 확인 | 없음 |

요청/응답 필드 상세(타입, 범위, null 허용 여부, 크로스필드 규칙)는 [공부시간 예측 API 계약](https://github.com/nhnacademy-aiot3-omagotchi/docs/blob/main/10-specifications/10-prediction/01-공부시간-예측-API-계약.md) 참고.

서비스 간 호출 인증(ADR 0013)은 아직 이 서비스에 적용되지 않았습니다 — 인프라 담당 영역으로 별도 처리 예정입니다.

## 예외 처리

- 요청 검증 실패: `400 COMMON_INVALID_REQUEST` (스택트레이스 미기록)
- 예측 중 예기치 못한 실패: `500 COMMON_INTERNAL_SERVER_ERROR` (원본 예외·스택트레이스 로그 보존)
- 경로 없음/메소드 불일치(404/405 등): FastAPI 기본 응답 형식 그대로 보존 — 팀 정책([공통 예외 처리](https://github.com/nhnacademy-aiot3-omagotchi/docs/blob/main/50-guides/04-error-handling.md))상 프레임워크가 만든 오류를 공통 형식으로 덮어쓰지 않음
- 모델 로드 실패: 원본 예외 전파 → 애플리케이션 기동 실패 ("로컬 실행" 절 참고)

`X-Request-ID`는 요청에 없으면 새로 발급하고, 응답 헤더·오류 본문의 `requestId`·서버 로그에 동일한 값을 사용합니다 ([ADR 0007](https://github.com/nhnacademy-aiot3-omagotchi/docs/blob/main/30-adr/0007-http-request-id-and-internal-service-communication.md)).

## Secret 관리

- 이 서비스가 직접 다루는 Secret 없음
- 모델 아티팩트(`models/study_time_model.joblib`)는 학습 산출물이라 저장소에 직접 커밋되어 있음 (ADR 0001)
