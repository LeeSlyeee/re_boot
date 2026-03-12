# 🎤 Re:Boot ERD 1분 발표 스크립트

---

## 오프닝 (5초)

> "Re:Boot의 데이터베이스는 **6개 도메인, 22개 핵심 테이블**로 구성되어 있습니다."

---

## 핵심 흐름 — 위에서 아래로 (40초)

### ① 모든 것의 시작은 `User`

> 학생과 교수자가 하나의 테이블에서 `role`로 구분되고, 취업/창업 목표(`career_goal`)가 이후 AI 커리큘럼의 분기 기준이 됩니다.

### ② 교수자가 `Lecture`를 개설하면, 라이브 수업 인프라가 펼쳐집니다

> `LiveSession` → 학생이 참여하면 → **실시간 STT 자막**(`LiveSTTLog`), **이해도 체크**(`PulseCheck`), **즉석 퀴즈**(`LiveQuiz`) — 이 3가지가 수업 중 동시에 돌아갑니다.

### ③ 수업이 끝나면 AI가 일합니다

> 자막 데이터가 → `SessionSummary`(AI 요약)로, 퀴즈 결과가 → `WeakZoneAlert`(취약점 알림)로 변환됩니다. 학생별로 `PlacementResult`(수준 진단)와 `ReviewRoute`(복습 경로)가 자동 생성됩니다.

### ④ 최종 목표는 커리어 자산화입니다

> 학습 이력이 `Portfolio`(이력서/사업계획서)로, `MockInterview`(AI 모의 면접)로 연결됩니다. **배운 걸 증명하는 것까지가 Re:Boot의 범위**입니다.

---

## 클로징 — 기술 강조 (10초)

> "기술적으로는 **PostgreSQL + pgvector**를 사용해 RAG 기반 벡터 검색을 지원하고, 모든 실시간 데이터는 **Django ORM + Polling** 아키텍처로 처리됩니다."

---

## 💡 발표 팁

| 전략 | 이유 |
|---|---|
| **ERD를 읽지 말고, 데이터 흐름을 이야기하세요** | 테이블 이름 나열은 청중이 기억 못함 |
| **손가락/포인터로 위→아래 흐름을 따라가세요** | User → Lecture → Live → AI → Career 순서 |
| **숫자 3개만 기억시키세요** | "22개 테이블, 실시간 3종 데이터, 최종 목표 커리어" |
| **"수업 중"과 "수업 후"를 구분하세요** | 이것이 Re:Boot의 차별점 (실시간 + 사후 AI) |

---

## 📊 시간 배분 가이드

```
[0:00 ~ 0:05]  오프닝 — 전체 규모 소개
[0:05 ~ 0:15]  ① User + Lecture — 기본 구조
[0:15 ~ 0:30]  ② 라이브 세션 — STT, Pulse, Quiz ★ 핵심
[0:30 ~ 0:45]  ③ AI 분석 — 요약, 취약점, 복습 경로 ★ 핵심
[0:45 ~ 0:55]  ④ 커리어 자산화 — Portfolio, MockInterview
[0:55 ~ 1:00]  클로징 — 기술 스택 한줄 요약
```

> **②번(라이브)과 ③번(AI)에 가장 많은 시간**을 쓰는 것이 좋습니다.
> 이 두 부분이 Re:Boot의 핵심 차별점이기 때문입니다.

---

## 🏗️ 6개 도메인 요약

| 도메인 | 핵심 테이블 | 역할 |
|---|---|---|
| 🩷 사용자 | `User` | role + career_goal로 전체 시스템 분기 |
| 🔵 수업 & 콘텐츠 | `Lecture`, `Syllabus`, `LectureMaterial` | 교수자가 생성하는 수업 구조 |
| 🟢 라이브 세션 | `LiveSession`, `LiveParticipant`, `LiveSTTLog`, `PulseCheck`, `LiveQuiz`, `LiveQuizResponse`, `WeakZoneAlert` | 실시간 수업 중 데이터 수집 |
| 🟡 개인 학습 | `LearningSession`, `STTLog`, `SessionSummary` | YouTube/오프라인 자습 기록 |
| 🟠 AI 분석 | `PlacementResult`, `SkillBlock`, `ReviewRoute`, `FormativeAssessment`, `AIChatSession`, `Curriculum` | 학습 수준 진단 + 적응형 경로 |
| 🟣 커리어 자산화 | `Portfolio`, `MockInterview` | 학습 → 취업/창업 문서화 |
