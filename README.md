# backend

## 폴더 구조 및 설명

### 최상위 폴더

*   `app/`: FastAPI 애플리케이션의 핵심 소스 코드가 위치합니다.
*   `test/`: 애플리케이션의 테스트 코드를 포함합니다.
*   `.env.example`: 애플리케이션 실행에 필요한 환경 변수 예시 파일입니다.
*   `Dockerfile`: 개발 환경용 Docker 이미지를 빌드하기 위한 설정 파일입니다.
*   `Dockerfile.prod`: 프로덕션 환경용 Docker 이미지를 빌드하기 위한 설정 파일입니다.
*   `docker-compose.yaml`: 개발 환경에서 Docker 컨테이너를 실행하기 위한 설정 파일입니다.
*   `docker-compose.prod.yaml`: 프로덕션 환경에서 Docker 컨테이너를 실행하기 위한 설정 파일입니다.
*   `README.md`: 현재 이 파일로, 프로젝트에 대한 개요와 사용법을 설명하는 문서입니다.

### `app/` 폴더

```text
app/
│
├── api/            # API 엔드포인트를 정의하는 라우터
│   └── v1/
│       ├── auth/
│       ├── chat/
│       ├── documents/
│       ├── groups/
│       ├── users/
│       └── health.py
│
├── core/           # 애플리케이션의 핵심 설정 (DB 연결, 미들웨어 등)
│   └── config.py
│
├── db/             # 데이터베이스 세션 및 초기화 관련 코드
│   └── session.py
│
├── errors/         # 커스텀 에러 핸들링 정의
│
├── main.py         # FastAPI 애플리케이션의 시작점
│
├── models/         # 데이터베이스 테이블과 SQLAlchemy 모델 정의
│
├── rag/            # RAG (Retrieval-Augmented Generation) 관련 모듈
│
├── resources/      # 애플리케이션에서 사용하는 정적 파일이나 리소스
│
├── schemas/        # Pydantic 스키마를 사용한 API 요청/응답 데이터 모델 정의
│
├── services/       # 비즈니스 로직을 처리하는 서비스 레이어
│
├── utils/          # 애플리케이션 전반에서 사용되는 유틸리티 함수
│
└── workers/        # 백그라운드 작업을 처리하는 Celery 워커 코드
    ├── celery_app.py
    └── tasks.py
```
