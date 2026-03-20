# Re:Boot Career Build-up Platform — 전체 구현 완료 리포트

> 최종 작성: 2026-02-20 | 최종 검증: 2026-02-23 (Phase 0~3 + 스킬블록 전체 코드 기반 교차 검증 완료)

---

## 📋 프로젝트 개요

Re:Boot Career Build-up Platform은 **AI 기반 실시간 강의 보조 시스템**으로,
교수자와 학습자 간의 상호작용을 극대화하고 데이터 기반 맞춤형 학습을 제공합니다.

---

## 🏗️ 아키텍처

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (Vue 3)                  │
│  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │  학습자 대시보드   │  │  교수자 대시보드 (P_dash) │  │
│  │  - 강의 참여      │  │  - 강의 관리              │  │
│  │  - 갭 맵         │  │  - 출석/퀴즈 분석         │  │
│  │  - 스킬블록      │  │  - 학습 분석 (Phase 3)    │  │
│  │  - 메시지 수신    │  │  - AI 제안 승인           │  │
│  └──────────────────┘  └──────────────────────────┘  │
└───────────────────────┬─────────────────────────────┘
                        │ REST API
┌───────────────────────┴─────────────────────────────┐
│              Backend (Django + DRF)                   │
│  ┌──────────┐ ┌────────────┐ ┌────────────────────┐  │
│  │ learning │ │ live_views │ │ analytics_views    │  │
│  │ views.py │ │ .py        │ │ skillblock_views   │  │
│  └──────────┘ └────────────┘ └────────────────────┘  │
│                       │                               │
│              ┌────────┴────────┐                      │
│              │  PostgreSQL DB  │                      │
│              │   38 Models     │                      │
│              └─────────────────┘                      │
└──────────────────────────────────────────────────────┘
```

---

## 📊 Phase별 구현 현황 (전체 완료 ✅)

### Phase 0: 라이브 세션 인프라

| 기능                         | 상태 |
| ---------------------------- | :--: |
| 실시간 라이브 세션 생성/관리 |  ✅  |
| 학생 입장 (코드 기반)        |  ✅  |
| STT 기록 + AI 노트 자동 생성 |  ✅  |
| 교수자 노트 검토/승인        |  ✅  |
| 결석생 노트 공개             |  ✅  |

### Phase 1: 수준 진단 + 갭 맵

| 기능                                | 상태 |
| ----------------------------------- | :--: |
| 진단 테스트 자동 생성               |  ✅  |
| BEGINNER/INTERMEDIATE/ADVANCED 분류 |  ✅  |
| 갭 맵 시각화 (카테고리별)           |  ✅  |
| 직무 목표별 필요 스킬 매핑          |  ✅  |

### Phase 2-1: 취약 구간 분석

| 기능                     | 상태 |
| ------------------------ | :--: |
| 퀴즈 오답 기반 자동 감지 |  ✅  |
| 펄스 혼란 기반 감지      |  ✅  |
| 보충 자료 자동 매칭      |  ✅  |
| 교수자 승인/거부         |  ✅  |

### Phase 2-2: 적응형 콘텐츠

| 기능                    | 상태 |
| ----------------------- | :--: |
| 레벨별 교안 자동 변형   |  ✅  |
| 교수자 승인 후 배포     |  ✅  |
| 학생별 맞춤 콘텐츠 제공 |  ✅  |

### Phase 2-3: 복습 루트 + 간격 반복

| 기능                          | 상태 |
| ----------------------------- | :--: |
| AI 복습 루트 자동 생성        |  ✅  |
| 교수자 승인/수정              |  ✅  |
| 간격 반복 (Spaced Repetition) |  ✅  |
| SM-2 알고리즘 기반 스케줄링   |  ✅  |

### Phase 2-4: 형성평가

| 기능                  | 상태 |
| --------------------- | :--: |
| AI 형성평가 자동 생성 |  ✅  |
| 학생 응답 + 자동 채점 |  ✅  |
| 교수자 분석 연동      |  ✅  |

### Phase 3: 교수자 분석 대시보드

| 기능                                           | 상태 |
| ---------------------------------------------- | :--: |
| 학습자 수준 현황판 (레벨 분포, 출석률, 진도율) |  ✅  |
| 위험군 학습자 자동 감지 (5가지 기준)           |  ✅  |
| 결석생 보충 학습 현황 추적 (NoteViewLog)       |  ✅  |
| 취약 구간 인사이트 (퀴즈+형성평가 통합)        |  ✅  |
| 차시별 비교 추이 차트                          |  ✅  |
| AI 제안 승인/거부 워크플로우                   |  ✅  |
| 강의 품질 리포트 (7가지 메트릭)                |  ✅  |
| 학생 레벨 재분류 제안 + 교수자 승인            |  ✅  |
| 그룹 메시지 발송 (레벨별/개별)                 |  ✅  |
| 학생 메시지 수신 + 읽음 처리                   |  ✅  |

### 스킬블록 시스템

| 기능                                                   | 상태 |
| ------------------------------------------------------ | :--: |
| 체크포인트+형성평가+이해도 기반 자동 생성              |  ✅  |
| 가중 평균 점수 (check 40% + formative 35% + pulse 25%) |  ✅  |
| 레벨별 이모지 (🌱씨앗 / 🌿새싹 / 🌸꽃)                 |  ✅  |
| 갭 맵 vs 스킬블록 비교 화면                            |  ✅  |
| 모의면접 연계 동기 부여 멘트                           |  ✅  |

---

## 🌐 API 엔드포인트 (총 44개)

### Router 기반 (10개 ViewSet)

```
/api/learning/sessions/        학습 세션
/api/learning/assessment/      평가
/api/learning/lectures/        강의 관리
/api/learning/rag/             RAG 검색
/api/learning/checklist/       체크리스트
/api/learning/live/            라이브 세션
/api/learning/materials/       교안 자료
/api/learning/placement/       수준 진단
/api/learning/goals/           목표 직무
/api/learning/gapmap/          갭 맵
```

### Path 기반 (34개)

```
Phase 0: 기본
  enroll/                                     수강 등록
  lectures/public/, lectures/my/              강의 목록
  live/join/                                  라이브 입장
  live/<pk>/note/                             노트 조회/수정
  live/<pk>/note/approve/                     노트 승인
  live/<pk>/note/materials/                   노트 교안 연결
  absent-notes/<lecture_id>/                  결석 노트 목록

Phase 1: 진단
  professor/<id>/diagnostics/                 교수자 진단 분석

Phase 2: AI 기능
  review-routes/my/                           내 복습 루트
  review-routes/<pk>/complete-item/           복습 항목 완료
  review-routes/pending/                      대기 복습 루트
  review-routes/<pk>/approve/                 복습 루트 승인
  review-routes/<pk>/                         복습 루트 수정
  spaced-repetition/due/                      간격 반복 due
  spaced-repetition/<pk>/complete/            간격 반복 완료
  formative/<id>/generate/                    형성평가 생성
  formative/<id>/                             형성평가 조회
  formative/<id>/submit/                      형성평가 제출
  materials/<pk>/generate-adaptive/           적응형 콘텐츠 생성
  materials/<pk>/adaptive/                    적응형 콘텐츠 조회
  adaptive/<pk>/approve/                      적응형 콘텐츠 승인
  live/<pk>/my-content/                       내 맞춤 콘텐츠

Phase 3: 교수자 분석
  professor/<id>/analytics/overview/          현황판
  professor/<id>/analytics/weak-insights/     취약구간
  professor/<id>/analytics/ai-suggestions/    AI 제안
  professor/<id>/analytics/quality-report/    품질 리포트
  professor/<id>/send-message/                개별 메시지
  professor/<id>/send-group-message/          그룹 메시지
  professor/<id>/apply-redistribution/        레벨 재분류
  messages/my/                                학생 메시지

스킬블록:
  skill-blocks/sync/<id>/                     블록 동기화
  skill-blocks/my/                            내 블록
  skill-blocks/interview-data/                면접 연계
```

---

## 📦 모델 구조도 (38개)

```
기본 인프라:
  Lecture → Syllabus → LearningObjective → StudentChecklist
  VectorStore, LearningSession, STTLog, SessionSummary
  DailyQuiz, QuizQuestion, QuizAttempt, AttemptDetail, RecordingUpload

라이브 세션:
  LiveSession → LiveParticipant, LiveSTTLog, LiveSessionNote
  PulseCheck → PulseLog
  LiveQuiz → LiveQuizResponse, LiveQuestion

AI 분석:
  WeakZoneAlert, AdaptiveContent
  ReviewRoute, SpacedRepetitionItem
  FormativeAssessment → FormativeResponse

수준 진단:
  Skill ← CareerGoal (M2M)
  PlacementQuestion, PlacementResult
  StudentGoal, StudentSkill

Phase 3:
  NoteViewLog (결석 노트 열람)
  GroupMessage (그룹 메시지 + read_by)
  SkillBlock (역량 블록)
```

---

## 🖥️ 프론트엔드 구조

### 학습자 대시보드 (`frontend/`)

- 강의 목록 + 수강 등록
- 라이브 세션 참여
- 갭 맵 시각화
- 간격 반복 퀴즈
- **교수자 메시지 수신 + 읽음**
- **스킬블록 카드 (이모지 + 갭맵 비교)**

### 교수자 대시보드 (`Professor_dashboard/`)

- 강의 생성/관리 (7개 탭)
- 진도 모니터링 + 출석 + 퀴즈 + 녹화
- 라이브 세션 운영 (실시간)
- 수준 진단 분석
- **📈 학습 분석 탭 (4개 서브탭)**:
  - 📊 현황판: 레벨 도넛 + 통계 카드 + 위험군 테이블
  - 🔍 취약구간: 오답 랭킹 + 차시 비교 차트
  - 🤖 AI 제안: 승인/거부 카드 + 판단 이력
  - 📋 리포트: 품질 메트릭 + 재분류 + 그룹 메시지

---

## ⚙️ 기술 스택

| 구분     | 기술                    |
| -------- | ----------------------- |
| Backend  | Django 5.2 + DRF        |
| Database | PostgreSQL + pgvector   |
| Frontend | Vue 3 (Composition API) |
| 차트     | Chart.js + vue-chartjs  |
| AI       | OpenAI API (GPT-4)      |
| 인증     | JWT (SimpleJWT)         |

---

## 🚀 실행 방법

```bash
# 백엔드
cd backend
source ../venv/bin/activate
python manage.py runserver 0.0.0.0:8000

# 교수자 대시보드
cd Professor_dashboard
npm run dev

# 학습자 프론트엔드
cd frontend
npm run dev
```
