# Phase 2: 강의 기능 고도화 — 구현 계획서

> 작성일: 2026-02-20  
> 전제: Phase 0 (라이브 세션 인프라) + Phase 1 (수준 진단 + 갭 맵) 완료

---

## 📋 Phase 2 전체 구조

```
Phase 2-1. Weak Zone Alert (부족 구간 알림)
     ↓ 데이터 의존
Phase 2-2. Adaptive Content Branching (수준별 콘텐츠 분기)
     ↓ 노트 의존
Phase 2-3. AI Review Suggestion (AI 복습 루트 제안)
     ↓ 오답 데이터 의존
Phase 2-4. Formative Assessment + Spaced Repetition (형성평가 + 간격 반복)
```

---

## Phase 2-1. 부족 구간 알림 (Weak Zone Alert)

### 개요

- 체크포인트 퀴즈 오답 + 펄스 "CONFUSED" 연속 입력 시 학습자에게 자동 알림
- 교수자에게 실시간 Weak Zone 발생 알림 + 보충 자료 푸시 승인

### 모델 설계

```python
class WeakZoneAlert(models.Model):
    """학습자의 취약 구간 감지 기록"""
    TRIGGER_CHOICES = (
        ('QUIZ_WRONG', '퀴즈 오답'),
        ('PULSE_CONFUSED', '연속 혼란 펄스'),
        ('COMBINED', '복합 (오답+혼란)'),
    )
    STATUS_CHOICES = (
        ('DETECTED', '감지됨'),
        ('MATERIAL_PUSHED', '보충 자료 전송됨'),
        ('DISMISSED', '교수자 거부'),
        ('RESOLVED', '해결됨'),
    )

    live_session = FK(LiveSession)
    student = FK(User)
    trigger_type = CharField(choices=TRIGGER_CHOICES)
    trigger_detail = JSONField()  # { quiz_ids: [], confused_count: 3, timestamp_range: "..." }
    status = CharField(choices=STATUS_CHOICES, default='DETECTED')
    supplement_material = FK(LectureMaterial, null=True)  # 교수자가 푸시한 보충 자료
    ai_suggested_content = TextField(blank=True)  # AI가 생성한 보충 설명
    created_at = DateTimeField(auto_now_add=True)
```

### API 설계

| 메서드 | 경로                                     | 역할                       | 주체   |
| ------ | ---------------------------------------- | -------------------------- | ------ |
| `GET`  | `/live/{id}/weak-zones/`                 | 현재 세션의 Weak Zone 목록 | 교수자 |
| `POST` | `/live/{id}/weak-zones/{wz_id}/push/`    | 보충 자료 푸시 승인        | 교수자 |
| `POST` | `/live/{id}/weak-zones/{wz_id}/dismiss/` | Weak Zone 거부 (무시)      | 교수자 |
| `GET`  | `/live/{id}/my-alerts/`                  | 내 Weak Zone 알림 조회     | 학습자 |
| `POST` | `/live/{id}/my-alerts/{wz_id}/resolve/`  | 알림 확인 처리             | 학습자 |

### 감지 로직 (백엔드 자동 트리거)

```
트리거 조건:
  1. 퀴즈 오답: 최근 2개 연속 오답 → QUIZ_WRONG
  2. 펄스 혼란: 3분 내 CONFUSED 2회 이상 → PULSE_CONFUSED
  3. 복합: 오답 1건 + CONFUSED 1건 동시 → COMBINED

발동 시점:
  - answerLiveQuiz() 응답 후 (오답 체크)
  - pulse 수신 후 (연속 혼란 체크)
```

### 프론트엔드

**학습자 (LearningView.vue)**

- 라이브 세션 중 Weak Zone 알림 팝업 (하단 슬라이드 업)
  - "📌 이 부분이 어려우신가요?"
  - [보충 자료 보기] 버튼 → 교수자 등록 자료 or AI 생성 설명
  - [괜찮아요] 버튼 → 알림 닫기
- 5초 폴링으로 `/my-alerts/` 체크

**교수자 (LectureDetailView.vue)**

- 라이브 세션 패널에 "⚠️ Weak Zone" 배지 (새 알림 카운트)
- 알림 리스트: 학생명(익명 번호) + 트리거 유형 + 타임스탬프
- [보충 자료 전송] / [무시] 버튼
  - 전송 시: 교안 목록에서 선택 or AI 자동 생성

### 예상 작업량: **~50분**

---

## Phase 2-2. 수준별 콘텐츠 분기 (Adaptive Content Branching)

### 개요

- 교수자 업로드 교안을 AI가 Level 1/2/3별로 변형 생성
- 학습자는 자신의 레벨에 맞는 자료 자동 수신 + 상위 레벨 도전 가능

### 모델 설계

```python
class AdaptiveContent(models.Model):
    """레벨별로 변형된 교안"""
    LEVEL_CHOICES = ((1, 'Level 1 - 기초'), (2, 'Level 2 - 표준'), (3, 'Level 3 - 심화'))
    STATUS_CHOICES = (
        ('DRAFT', 'AI 생성 초안'),
        ('APPROVED', '교수자 승인'),
        ('REJECTED', '교수자 거부'),
    )

    source_material = FK(LectureMaterial)  # 원본 교안
    level = IntegerField(choices=LEVEL_CHOICES)
    title = CharField(max_length=200)
    content = TextField()  # AI가 변형한 마크다운 콘텐츠
    status = CharField(choices=STATUS_CHOICES, default='DRAFT')
    created_at = DateTimeField(auto_now_add=True)
    approved_at = DateTimeField(null=True)

    class Meta:
        unique_together = ['source_material', 'level']
```

### API 설계

| 메서드  | 경로                                 | 역할                       | 주체   |
| ------- | ------------------------------------ | -------------------------- | ------ |
| `POST`  | `/materials/{id}/generate-adaptive/` | AI로 3레벨 변형 생성       | 교수자 |
| `GET`   | `/materials/{id}/adaptive/`          | 해당 교안의 변형 버전 목록 | 교수자 |
| `PATCH` | `/adaptive/{id}/`                    | 변형 내용 수정             | 교수자 |
| `POST`  | `/adaptive/{id}/approve/`            | 변형 승인                  | 교수자 |
| `GET`   | `/live/{id}/my-content/`             | 내 레벨에 맞는 자료 조회   | 학습자 |

### AI 변형 생성 규칙

```
GPT-4o-mini 프롬프트:
  원본 교안 텍스트를 입력으로 받아 3개 레벨로 변형 생성

  Level 1 (기초):
    - 전문 용어를 쉬운 표현으로 대체
    - 비유와 일상 예시 추가
    - 핵심 3줄 요약 + 단계별 설명

  Level 2 (표준):
    - 원본과 유사하되 핵심 개념 강조
    - 실습 문제 2~3개 추가
    - 코드 예시 포함

  Level 3 (심화):
    - 심화 개념과 이론 추가
    - "더 나아가기" 확장 과제
    - 실무 적용 사례 + 관련 논문/아티클 링크
```

### 프론트엔드

**교수자 (LectureDetailView.vue)**

- 교안 업로드 섹션에 [🤖 레벨별 자동 변형] 버튼
- 생성 결과: Level 1/2/3 탭 전환 미리보기
- 각 레벨별 [승인] / [수정] / [거부] 버튼

**학습자 (LearningView.vue)**

- 라이브 세션 중 자신의 레벨에 맞는 자료 자동 표시
- 우측 상단 레벨 전환 토글: "Lv2 ▸ Lv3 도전" (선택적)
- 상위 레벨 자료 열람 시 별도 플래그 (갭 맵 연동 가능)

### 의존성

- Phase 1의 `PlacementResult.level` (학습자 레벨)
- `LectureMaterial` (원본 교안)

### 예상 작업량: **~1시간**

---

## Phase 2-3. AI 복습 루트 제안 (AI Review Suggestion)

### 개요

- 세션 종료 후 "오늘 이 순서로 복습하세요" AI 루트 자동 생성
- 에빙하우스 망각 곡선 기반 간격 복습 알림

### 모델 설계

```python
class ReviewRoute(models.Model):
    """세션별 AI 복습 루트"""
    STATUS_CHOICES = (
        ('SUGGESTED', 'AI 제안'),
        ('APPROVED', '교수자 승인'),
        ('MODIFIED', '교수자 수정'),
        ('REJECTED', '교수자 거부'),
    )

    live_session = FK(LiveSession)
    student = FK(User)
    items = JSONField()
    # items 구조:
    # [
    #   { "order": 1, "type": "note", "title": "오늘 통합 노트", "note_id": 5, "est_minutes": 10 },
    #   { "order": 2, "type": "concept", "title": "클로저 개념 복습", "content": "...", "est_minutes": 5 },
    #   { "order": 3, "type": "prev_session", "title": "지난주 스코프 복습", "note_id": 3, "est_minutes": 8 },
    #   { "order": 4, "type": "preview", "title": "내일 배울 Promise 선행", "content": "...", "est_minutes": 5 },
    # ]
    status = CharField(choices=STATUS_CHOICES, default='SUGGESTED')
    total_est_minutes = IntegerField(default=0)
    completed_items = JSONField(default=list)  # [1, 2] = 1번, 2번 완료
    created_at = DateTimeField(auto_now_add=True)


class SpacedRepetitionItem(models.Model):
    """에빙하우스 간격 반복 스케줄"""
    student = FK(User)
    concept_name = CharField(max_length=200)  # "클로저", "Promise"
    source_session = FK(LiveSession, null=True)
    source_quiz = FK(LiveQuiz, null=True)  # 오답이 발생한 퀴즈
    review_question = TextField()  # 빠른 확인용 1문항
    review_answer = CharField(max_length=500)
    # 간격 반복 스케줄
    schedule = JSONField()
    # [
    #   { "review_num": 1, "due_at": "2026-02-21T09:00", "completed": false },  # 1일 후
    #   { "review_num": 2, "due_at": "2026-02-23T09:00", "completed": false },  # 3일 후
    #   { "review_num": 3, "due_at": "2026-02-27T09:00", "completed": false },  # 7일 후
    #   { "review_num": 4, "due_at": "2026-03-20T09:00", "completed": false },  # 1개월 후
    # ]
    current_review = IntegerField(default=0)  # 현재 몇 차 복습까지 완료
    created_at = DateTimeField(auto_now_add=True)
```

### API 설계

| 메서드  | 경로                                 | 역할                     | 주체                       |
| ------- | ------------------------------------ | ------------------------ | -------------------------- |
| `POST`  | `/live/{id}/review-route/generate/`  | AI 복습 루트 자동 생성   | 시스템 (세션 종료 시 자동) |
| `GET`   | `/review-routes/my/`                 | 내 복습 루트 목록        | 학습자                     |
| `POST`  | `/review-routes/{id}/complete-item/` | 특정 복습 항목 완료 체크 | 학습자                     |
| `GET`   | `/review-routes/pending/`            | 교수자 승인 대기 루트    | 교수자                     |
| `POST`  | `/review-routes/{id}/approve/`       | 루트 승인                | 교수자                     |
| `PATCH` | `/review-routes/{id}/`               | 루트 수정 (항목 교체)    | 교수자                     |
| `GET`   | `/spaced-repetition/due/`            | 오늘 복습할 항목         | 학습자                     |
| `POST`  | `/spaced-repetition/{id}/complete/`  | 복습 완료                | 학습자                     |

### AI 복습 루트 생성 로직

```
세션 종료 시 _generate_live_note() 이후 자동 실행:

입력:
  - 오늘 오답 개념 목록 (퀴즈 데이터)
  - 이전 세션의 관련 개념 (STT 키워드 매칭)
  - 다음 세션 예정 주제 (있는 경우)
  - 학습자의 갭 맵 현황

출력:
  1순위: 오늘 통합 노트 (무조건 첫 번째)
  2순위: 오답 개념 정리 (각 3~5분)
  3순위: 이전 강의 관련 개념 (연결 고리)
  4순위: 다음 강의 선행 개념 (미리보기)

간격 반복 스케줄:
  오답 개념마다 SpacedRepetitionItem 자동 생성
  1차: +1일 / 2차: +3일 / 3차: +7일 / 4차: +30일
```

### 프론트엔드

**학습자 (새 컴포넌트: ReviewRoutePanel)**

- 세션 종료 후 "📚 오늘의 복습 루트" 카드
- 체크리스트 형태: [ ] 통합 노트 읽기 (10분) → [ ] 클로저 복습 (5분) → ...
- 각 항목 클릭 시 내용 펼침
- 상단: "오늘 예상 복습 시간: 28분"

**학습자 대시보드 (DashboardView.vue)**

- "🔔 오늘 복습할 항목 N개" 배지
- 간격 반복 알림: "3일 전 배운 클로저 개념, 기억하세요?" → 1문항 퀴즈

**교수자 (LectureDetailView.vue)**

- 복습 루트 승인 리스트 (간략 표시)
- [승인] / [수정] / [거부] 버튼

### 예상 작업량: **~1시간 30분**

---

## Phase 2-4. 형성평가 + 간격 반복 연계 (Formative Assessment + Spaced Repetition)

### 개요

- 통합 노트 기반 사후 형성평가 문항 자동 생성 (GPT-4o-mini)
- 학습자 풀이 → 오답 개념 → 갭 맵 업데이트 + 간격 반복 스케줄 자동 등록

### 모델 설계

```python
class FormativeAssessment(models.Model):
    """사후 형성평가"""
    STATUS_CHOICES = (
        ('DRAFT', 'AI 생성 초안'),
        ('APPROVED', '교수자 승인'),
        ('ACTIVE', '학습자 배포됨'),
        ('CLOSED', '마감'),
    )

    live_session_note = FK(LiveSessionNote)  # 기반 노트
    questions = JSONField()
    # [
    #   {
    #     "id": 1,
    #     "question": "클로저란 무엇인가?",
    #     "options": ["A", "B", "C", "D"],
    #     "correct_answer": "B",
    #     "explanation": "...",
    #     "related_note_section": "## 핵심 내용 정리 > 1. 클로저",  # 노트 내 위치
    #     "concept_tag": "클로저",  # 갭 맵 연동용
    #   },
    #   ...
    # ]
    status = CharField(choices=STATUS_CHOICES, default='DRAFT')
    deadline_hours = IntegerField(default=24)  # 풀이 권장 시간 (시간 단위)
    created_at = DateTimeField(auto_now_add=True)
    approved_at = DateTimeField(null=True)


class FormativeResponse(models.Model):
    """학습자의 형성평가 응답"""
    assessment = FK(FormativeAssessment)
    student = FK(User)
    answers = JSONField()  # { "1": "A", "2": "B", ... }
    score = IntegerField(default=0)
    total = IntegerField(default=0)
    wrong_concepts = JSONField(default=list)  # ["클로저", "스코프"]
    completed_at = DateTimeField(auto_now_add=True)
```

### API 설계

| 메서드  | 경로                       | 역할                     | 주체   |
| ------- | -------------------------- | ------------------------ | ------ |
| `POST`  | `/formative/generate/`     | 노트 기반 형성평가 생성  | 교수자 |
| `GET`   | `/formative/{id}/`         | 형성평가 조회            | 교수자 |
| `PATCH` | `/formative/{id}/`         | 문항 수정                | 교수자 |
| `POST`  | `/formative/{id}/approve/` | 승인 → 학습자 배포       | 교수자 |
| `GET`   | `/formative/my-pending/`   | 내 미완료 형성평가       | 학습자 |
| `POST`  | `/formative/{id}/submit/`  | 형성평가 제출            | 학습자 |
| `GET`   | `/formative/{id}/result/`  | 내 결과 + 오답 노트 연결 | 학습자 |

### AI 자동 생성 로직

```
입력: LiveSessionNote.content (통합 노트 마크다운)

GPT-4o-mini 프롬프트:
  "아래 강의 노트를 기반으로 핵심 개념 확인용 형성평가 3~5문항을 생성하세요.

   각 문항 형식:
   - 4지선다
   - 정답 + 해설
   - 노트 내 관련 섹션 제목 (정확한 헤딩)
   - 핵심 개념 태그 (1~2 단어)

   난이도: 기억 확인 수준 (부담 없는 저부하 설계)
   목적: 수업 내용을 제대로 이해했는지 자기 점검"
```

### 형성평가 → 간격 반복 연계 플로우

```
학습자 형성평가 제출
  ↓
채점 + 오답 개념 추출 (wrong_concepts)
  ↓
각 오답 개념마다:
  1. StudentSkill 갭 맵 업데이트 (progress 감소 or status='LEARNING')
  2. SpacedRepetitionItem 자동 생성
     - 1차: +1일 / 2차: +3일 / 3차: +7일 / 4차: +30일
     - 각 복습은 1문항 미니 퀴즈 (AI 자동 생성)
  ↓
학습자 대시보드에 간격 반복 알림 표시
```

### 프론트엔드

**교수자 (LectureDetailView.vue)**

- 인사이트 리포트 하단 또는 세션 히스토리에 [📝 형성평가 생성] 버튼
- AI 초안 미리보기 → 문항별 수정 → [승인 & 배포]

**학습자 (LearningView.vue or 별도 뷰)**

- 세션 종료 후 or 대시보드에서 "📝 형성평가 N건 미완료" 배지
- [오늘 배운 내용 확인하기] → 3~5문항 풀이
- 결과 화면: 정답/오답 + 해설 + "📖 노트에서 확인" 링크
- 오답 개념 → 갭 맵 자동 업데이트 안내

**학습자 대시보드 (DashboardView.vue)**

- 간격 반복 알림: "🔔 3일 전 배운 클로저, 기억하세요?" → [30초 퀴즈]

### 의존성

- Phase 0-6: `LiveSessionNote.content` (통합 노트)
- Phase 1: `StudentSkill` (갭 맵 업데이트)
- Phase 2-3: `SpacedRepetitionItem` (간격 반복 모델 공유)

### 예상 작업량: **~1시간 30분**

---

## 📊 구현 순서 + 예상 일정

| 순서  | Step                       | 핵심 산출물                              | 의존성                         | 예상 시간  |
| ----- | -------------------------- | ---------------------------------------- | ------------------------------ | ---------- |
| **1** | 2-1 Weak Zone Alert        | WeakZoneAlert 모델 + 감지 로직 + 양쪽 UI | Phase 0 (퀴즈/펄스)            | 50분       |
| **2** | 2-3 AI Review + Spaced Rep | ReviewRoute + SpacedRepetitionItem 모델  | Phase 0 (노트)                 | 1시간 30분 |
| **3** | 2-4 Formative Assessment   | FormativeAssessment + FormativeResponse  | Phase 0 (노트) + 2-3 (SR 모델) | 1시간 30분 |
| **4** | 2-2 Adaptive Content       | AdaptiveContent 모델 + AI 변형           | Phase 1 (레벨)                 | 1시간      |

> **총 예상: ~5시간**

### 순서 조정 이유

1. **2-1 → 2-3 순서**: Weak Zone 데이터가 복습 루트의 우선순위 결정에 활용됨
2. **2-3을 2-4보다 먼저**: SpacedRepetitionItem 모델을 2-3에서 만들고 2-4에서 재사용
3. **2-2는 마지막**: 독립적이며, 다른 기능이 없어도 동작 가능. 레벨 데이터만 필요

---

## 🗂️ 파일 변경 예상

### 백엔드 신규 파일

```
backend/learning/
├── models.py                 # +4 모델 (WeakZone, AdaptiveContent, ReviewRoute, Formative 등)
├── weak_zone_views.py        # Phase 2-1 API (NEW)
├── adaptive_views.py         # Phase 2-2 API (NEW)
├── review_views.py           # Phase 2-3 API (NEW)
├── formative_views.py        # Phase 2-4 API (NEW)
├── urls.py                   # URL 등록 추가
└── admin.py                  # Admin 등록 추가
```

### 프론트엔드 변경

```
frontend/src/
├── views/LearningView.vue       # Weak Zone 팝업 + 복습 루트 + 형성평가
├── views/DashboardView.vue      # 간격 반복 알림 + 형성평가 미완료 배지
└── views/ReviewRouteView.vue    # 복습 루트 전용 뷰 (NEW)

Professor_dashboard/src/
├── views/LectureDetailView.vue  # Weak Zone 관리 + 적응형 콘텐츠 + 루트 승인 + 형성평가
```

---

## ⚠️ 리스크 및 주의사항

| 리스크           | 영향                                             | 대응                                                            |
| ---------------- | ------------------------------------------------ | --------------------------------------------------------------- |
| AI API 비용      | 변형 생성 + 형성평가 + 복습 문항 = GPT 호출 다수 | `gpt-4o-mini` 사용으로 비용 절감                                |
| 간격 반복 cron   | 매일 알림을 보내려면 스케줄러 필요               | 1차: 프론트 접속 시 due 체크 (폴링) / 2차: Celery 등 백그라운드 |
| 교수자 승인 병목 | 모든 기능에 승인 절차 있음                       | 자동 승인 옵션 (교수자 설정에서 ON/OFF) 제공                    |
| 데이터 불충분    | 세션 데이터가 적을 때 AI 품질 저하               | Fallback 기본 루트 + "데이터 부족" 안내 메시지                  |

---

## ✅ 체크리스트

### Phase 2-1. Weak Zone Alert

- [ ] `WeakZoneAlert` 모델 생성 + 마이그레이션
- [ ] 감지 로직 (퀴즈 오답/펄스 혼란 후 자동 트리거)
- [ ] 교수자: Weak Zone 목록 + 푸시/거부 UI
- [ ] 학습자: Weak Zone 알림 팝업 + 보충 자료 열기

### Phase 2-2. Adaptive Content Branching

- [ ] `AdaptiveContent` 모델 생성 + 마이그레이션
- [ ] AI 교안 변형 생성 API (GPT-4o-mini)
- [ ] 교수자: 레벨별 미리보기 + 승인/수정/거부 UI
- [ ] 학습자: 본인 레벨 자료 자동 표시 + 레벨 전환 토글

### Phase 2-3. AI Review Suggestion

- [ ] `ReviewRoute` + `SpacedRepetitionItem` 모델 생성
- [ ] 세션 종료 시 AI 복습 루트 자동 생성
- [ ] 학습자: 복습 루트 체크리스트 + 진행률
- [ ] 교수자: 루트 승인/수정/거부 UI
- [ ] 간격 반복: due 항목 조회 + 미니 퀴즈 풀이

### Phase 2-4. Formative Assessment

- [ ] `FormativeAssessment` + `FormativeResponse` 모델 생성
- [ ] AI 형성평가 자동 생성 API (노트 기반)
- [ ] 교수자: 문항 검토 + 승인 & 배포 UI
- [ ] 학습자: 형성평가 풀이 + 결과 + 오답→노트 바로가기
- [ ] 오답 개념 → 갭 맵 업데이트 + 간격 반복 자동 등록
