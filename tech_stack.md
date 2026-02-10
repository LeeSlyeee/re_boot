# 🛠️ 기술 스택 및 아키텍처 (Technology Stack & Architecture)

> Re:Boot 서비스 기획(`service_specification.md`) 구현을 위한 최적화된 기술셋 정의

## 1. 개요 (Overview)

본 프로젝트는 **빠른 개발 생산성(High Velocity)**과 **강력한 AI 연동성(AI-Native)**을 목표로 합니다.
Python 기반의 Django 생태계를 통해 복잡한 비즈니스 로직(커리큘럼 리라우팅)을 처리하고, Vue.js를 통해 사용자 친화적인 인터랙티브 UI를 제공합니다.

---

## 2. 프론트엔드 (Frontend) - Interactive Web App

학습자의 몰입도를 높이기 위한 SPA(Single Page Application) 구조.

- **Framework**: **Vue.js 3 (Composition API)**
  - _이유_: 직관적인 문법과 높은 생산성, React 대비 빠른 러닝 커브.
- **Build Tool**: **Vite**
  - _이유_: 매우 빠른 HMR(Hot Module Replacement)로 개발 경험 극대화.
- **State Management**: **Pinia** (or Reactivity API ref/reactive)
  - _이유_: 실시간 학습 상태(STT 로딩, 퀴즈 점수 등)를 전역에서 효율적으로 관리.
- **Styling**: **SCSS / Vanilla CSS** (Glassmorphism Design)
  - _이유_: 유연한 커스터마이징, 고급스러운 UI 연출.
- **Visualizations**: **Chart.js** (또는 ApexCharts)
  - _용도_: 학습 성취도 그래프, 기술 블록(Skill Block) 시각화.
- **Audio Processing**: **Web Audio API** (MediaRecorder)
  - _용도_: 브라우저에서 마이크/시스템 오디오 캡처 및 청크 단위 전송.

---

## 3. 백엔드 (Backend) - Logic & API Server

안정적인 데이터 처리와 Python 생태계의 풍부한 AI 라이브러리 활용.

- **Framework**: **Django Rest Framework (DRF)**
  - _이유_: 강력한 ORM, 인증 시스템, Python 기반의 AI 라이브러리 연동 용이성.
- **Database**: **SQLite** (Dev) / **PostgreSQL** (Prod - _권장_)
  - _이유_: JSONField 지원(커리큘럼 구조 저장), 복잡한 관계형 데이터(강의-세션-퀴즈) 처리.
- **Async Processing**: **Celery + Redis** (Optional / Future)
  - _용도_: 긴 시간이 소요되는 AI 분석 작업(영상 전체 요약, 리라우팅 계산) 비동기 처리.

---

## 4. 인공지능 및 데이터 (AI & Data) - The Core Brain

서비스의 핵심인 '지능형 튜터'와 '자동화'를 담당.

- **LLM (Large Language Models)**: **OpenAI GPT-4o**
  - _용도_: 강의 요약, 퀴즈 생성, 맞춤형 피드백 생성, 튜터링 챗봇.
  - _전략_: Prompt Engineering을 통해 페르소나(친절한 튜터/깐깐한 면접관) 부여.
- **STT (Speech-to-Text)**: **OpenAI Whisper (API)**
  - _용도_: 강의 음성의 고정확도 텍스트 변환.
- **RAG (Retrieval-Augmented Generation)**: **LangChain** (Optional)
  - _용도_: "아까 선생님이 말한 예시"를 찾기 위해 벡터 유사도 검색 활용.
  - _저장소_: **FAISS** 또는 **ChromaDB** (임시 메모리).

---

## 5. 인프라 및 배포 (Infrastructure)

- **Cloud Provider**: **OCI (Oracle Cloud Infrastructure)**
  - _이유_: 비용 효율성 및 고성능 인스턴스 활용.
- **Web Server**: **Nginx**
  - _용도_: 리버스 프록시, 정적 파일 서빙, SSL 처리.
- **Process Manager**: **Gunicorn + Systemd**
  - _용도_: Python WSGI 애플리케이션의 안정적 구동.

---

## 6. 핵심 기능별 기술 매핑 (Feature Implementation Strategy)

| 기능 (Feature)           | 주요 기술 (Tech)                            | 구현 전략 (Strategy)                                                     |
| :----------------------- | :------------------------------------------ | :----------------------------------------------------------------------- |
| **실시간 STT**           | MediaRecorder API -> Backend API -> Whisper | 오디오를 3~10초 단위 청크(Chunk)로 분할 전송하여 실시간성 확보.          |
| **학습 분절/체크포인트** | Django Models (ORM)                         | `Session`, `Checkpoint` 모델 간의 1:N 관계 설정 및 상태(Pass/Fail) 관리. |
| **지능형 리라우팅**      | Python Logic (NumPy/Pandas)                 | 학생의 성취도 벡터와 커리큘럼 난이도를 매칭하여 최적 경로 재계산.        |
| **스킬 블록 자산화**     | JSON / RDB                                  | 획득한 스킬을 구조화된 데이터(JSON)로 저장하여 포트폴리오 생성 시 파싱.  |

---

## 7. 보안 및 정책 (Security & Policy)

- **Data Privacy**: 원본 음성 파일은 처리(STT 변환) 즉시 삭제. 텍스트화된 데이터만 DB에 암호화 저장.
- **Authentication**: JWT (JSON Web Token) 기반 인증으로 확장성 확보.
