# Phase 2: 강의 기능 고도화 — 구현 계획서 (v2 점검 완료)

> 작성일: 2026-02-20  
> v2 점검: 2026-02-20 18:25 — 기존 코드베이스 교차 검증 완료  
> 전제: Phase 0 (라이브 세션 인프라) + Phase 1 (수준 진단 + 갭 맵) 완료

---

## 🔍 점검 완료 — 발견된 이슈 8건

### ⚠️ 즉시 수정 필요 (Phase 2 구현 전 전처리)

| #     | 이슈                              | 위치                         | 영향                                                                                                      | 대응                                                                                                  |
| ----- | --------------------------------- | ---------------------------- | --------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| **1** | `PulseCheck` unique_together 제약 | `models.py:326`              | 학생당 세션 1건만 유지 → "3분 내 CONFUSED 2회" 감지 불가                                                  | `PulseLog` 히스토리 모델 신규 추가 (기존 PulseCheck은 "현재 상태"로 유지, PulseLog은 "이력"으로 분리) |
| **2** | `lectureMaterials` 변수명 불일치  | `LectureDetailView.vue:1421` | Step E 교안 매핑 UI가 `lectureMaterials`를 참조하지만, 실제 변수명은 `materials` (line 218) → 런타임 에러 | 교안 매핑 UI의 `lectureMaterials`를 `materials`로 수정                                                |
| **3** | 명세의 "5주기 암기법" 미반영      | 계획서 Phase 2-3             | 명세에는 10분/1일/1주/1개월/6개월 5단계, 계획서에는 1일/3일/7일/30일 4단계                                | 명세 기준으로 5주기로 수정                                                                            |

### ⚠️ 설계 보완 필요

| #     | 이슈                                         | 설명                                                                                   | 대응                                                          |
| ----- | -------------------------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| **4** | `concept_tag` → `StudentSkill` 매핑 불명확   | 형성평가 오답의 concept_tag (예: "클로저")를 `Skill.name`과 어떻게 매핑할지 명시 안 됨 | 부분 일치 + AI 매핑 Fallback 방식 명시                        |
| **5** | `LectureMaterial` 텍스트 추출 미기재         | 2-2 적응형 콘텐츠에서 원본 교안(PDF/PPT)의 텍스트를 어떻게 추출할지 방법 없음          | (1차) 마크다운 교안만 지원, (2차) PDF→텍스트 파이프라인 추가  |
| **6** | `DashboardView.vue` 복습 알림 통합 위치      | 기존 대시보드에 간격 반복 알림을 어디에 넣을지 구체적 위치 미결정                      | 상단 헤더 아래 "오늘의 할 일" 섹션에 배치                     |
| **7** | Weak Zone `ai_suggested_content` 생성 타이밍 | 교수자 푸시 전에 AI가 보충 설명을 미리 생성해야 하는지, 푸시 시점에 생성하는지         | 감지 시점에 AI 미리 생성 → 교수자가 확인 후 푸시              |
| **8** | ReviewRoute 교수자 승인 병목                 | 모든 복습 루트에 교수자 승인 필수 → 학생 N명 × 세션 M개 = 승인 폭발                    | 자동 승인 기본값 → 교수자가 "수동 승인 모드" 선택 시에만 대기 |

---

## 📋 Phase 2 전체 구조 (수정됨)

```
[전처리] PulseLog 모델 + lectureMaterials 변수 수정 (~10분)
     ↓
Phase 2-1. Weak Zone Alert (부족 구간 알림)        [~50분]
     ↓ WeakZone 데이터가 복습 루트 우선순위에 반영
Phase 2-3. AI Review + Spaced Repetition           [~1시간 30분]
     ↓ SpacedRepetitionItem 모델을 2-4에서 재사용
Phase 2-4. Formative Assessment + SR 연계          [~1시간 30분]
     ↓ (독립)
Phase 2-2. Adaptive Content Branching              [~1시간]
```

---

## [전처리] 필수 사전 작업 (~10분)

### 1. PulseLog 히스토리 모델 추가

```python
class PulseLog(models.Model):
    """펄스 이력 (Weak Zone 감지용). PulseCheck과 별도로 모든 펄스를 기록."""
    live_session = FK(LiveSession, related_name='pulse_logs')
    student = FK(User)
    pulse_type = CharField(max_length=12, choices=PulseCheck.PULSE_CHOICES)
    created_at = DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
```

- 기존 `PulseCheck`은 "현재 상태" (unique_together 유지)
- `PulseLog`는 "이력" (Weak Zone 감지에 사용)
- 펄스 수신 API (`pulse/`)에서 PulseCheck update_or_create + PulseLog.create 동시 수행

### 2. lectureMaterials → materials 변수 수정

`LectureDetailView.vue`의 교안 매핑 UI에서 `lectureMaterials`를 `materials`로 수정 (3곳)

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

    live_session = FK(LiveSession, related_name='weak_zones')
    student = FK(User)
    trigger_type = CharField(choices=TRIGGER_CHOICES)
    trigger_detail = JSONField()
    # 예시: { "quiz_ids": [12, 15], "confused_count": 3, "recent_topic": "클로저" }
    status = CharField(choices=STATUS_CHOICES, default='DETECTED')
    supplement_material = FK(LectureMaterial, null=True, blank=True)
    ai_suggested_content = TextField(blank=True)  # 감지 시점에 AI가 즉시 생성
    created_at = DateTimeField(auto_now_add=True)
```

### 감지 로직 (수정됨 — PulseLog 사용)

```
[트리거 1: 퀴즈 오답]
  answer_quiz() API 내부에서 is_correct=False일 때:
    → 해당 학생의 최근 2개 LiveQuizResponse 확인
    → 연속 2개 오답 → WeakZoneAlert(QUIZ_WRONG) 생성

[트리거 2: 펄스 혼란] ← PulseLog 사용
  pulse() API에서 pulse_type='CONFUSED'일 때:
    → PulseLog에서 최근 3분 이내 CONFUSED 이력 조회
    → 2건 이상 → WeakZoneAlert(PULSE_CONFUSED) 생성

[트리거 3: 복합]
  오답 1건 + 3분 내 CONFUSED 1건 동시 감지 → COMBINED

[중복 방지]
  동일 학생 + 동일 세션에서 5분 이내 동일 trigger_type의 Alert가 이미 존재하면 Skip

[AI 보충 설명 자동 생성]
  Alert 생성 시 GPT-4o-mini로 즉시 생성 (비동기 optional)
  프롬프트: "학생이 '{trigger_detail.recent_topic}' 개념에서 어려움을 겪고 있습니다.
            쉬운 설명 + 예시 1개를 200자 이내로 작성하세요."
```

### API 설계

| 메서드 | 경로                                     | 역할                                           | 주체   |
| ------ | ---------------------------------------- | ---------------------------------------------- | ------ |
| `GET`  | `/live/{id}/weak-zones/`                 | 현재 세션의 Weak Zone 목록                     | 교수자 |
| `POST` | `/live/{id}/weak-zones/{wz_id}/push/`    | 보충 자료 푸시 (material_id 또는 AI 설명 사용) | 교수자 |
| `POST` | `/live/{id}/weak-zones/{wz_id}/dismiss/` | Weak Zone 거부 (무시)                          | 교수자 |
| `GET`  | `/live/{id}/my-alerts/`                  | 내 Weak Zone 알림 조회 (미해결만)              | 학습자 |
| `POST` | `/live/{id}/my-alerts/{wz_id}/resolve/`  | 알림 확인 처리                                 | 학습자 |

### 프론트엔드

**학습자 (LearningView.vue)**

- 라이브 세션 중 하단 슬라이드 업 팝업
  - "📌 이 부분이 어려우신가요?"
  - AI 생성 설명 표시 or 보충 자료 링크
  - [보충 자료 보기] / [괜찮아요] 버튼
- 기존 5초 폴링에 `/my-alerts/` 체크 추가

**교수자 (LectureDetailView.vue)**

- 라이브 세션 패널에 "⚠️ Weak Zone (N)" 배지
- 목록: 학생 번호 + 트리거 유형 + AI 보충 설명 미리보기
- [보충 자료 전송] → 교안 선택 모달 or [AI 설명 그대로 전송]
- [무시] → status=DISMISSED

### 예상 작업량: ~50분

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

    source_material = FK(LectureMaterial)
    level = IntegerField(choices=LEVEL_CHOICES)
    title = CharField(max_length=200)
    content = TextField()  # AI 변형 마크다운
    status = CharField(choices=STATUS_CHOICES, default='DRAFT')
    created_at = DateTimeField(auto_now_add=True)
    approved_at = DateTimeField(null=True)

    class Meta:
        unique_together = ['source_material', 'level']
```

### AI 변형 생성 (보완: 텍스트 추출)

```
교안 텍스트 추출:
  1차: file_type='MD' → 파일 내용 직접 사용
  2차: file_type='PDF' → backend에 PyMuPDF(fitz) 설치 후 텍스트 추출
  3차: file_type='PPT' → python-pptx로 슬라이드 텍스트 추출
  미지원: 에러 반환 "이 형식은 자동 변형이 지원되지 않습니다"

GPT-4o-mini 프롬프트:
  Level 1: 전문 용어 → 쉬운 표현, 비유·일상 예시, 핵심 3줄 요약
  Level 2: 원본 유지 + 핵심 강조, 실습 문제 2~3개 추가
  Level 3: 심화 개념·이론, "더 나아가기" 확장 과제, 실무 사례
```

### API 설계

| 메서드  | 경로                                 | 역할               | 주체   |
| ------- | ------------------------------------ | ------------------ | ------ |
| `POST`  | `/materials/{id}/generate-adaptive/` | AI 3레벨 변형 생성 | 교수자 |
| `GET`   | `/materials/{id}/adaptive/`          | 변형 버전 목록     | 교수자 |
| `PATCH` | `/adaptive/{id}/`                    | 변형 내용 수정     | 교수자 |
| `POST`  | `/adaptive/{id}/approve/`            | 변형 승인          | 교수자 |
| `GET`   | `/live/{id}/my-content/`             | 내 레벨 자료 조회  | 학습자 |

### 프론트엔드

**교수자 (LectureDetailView.vue)**

- 교안 업로드 섹션에 [🤖 레벨별 변형] 버튼
- Level 1/2/3 탭 미리보기 + 각 [승인/수정/거부]

**학습자 (LearningView.vue)**

- 세션 중 레벨별 자료 자동 표시 + 상위 레벨 도전 토글

### 의존성

- `PlacementResult.level` (Phase 1)
- `LectureMaterial` (원본 교안)

### 예상 작업량: ~1시간

---

## Phase 2-3. AI 복습 루트 제안 (AI Review Suggestion)

### 개요

- 세션 종료 후 학생별 복습 루트 자동 생성
- 에빙하우스 5주기 간격 복습 (명세 기준)

### 모델 설계

```python
class ReviewRoute(models.Model):
    """세션별 학생 맞춤 AI 복습 루트"""
    STATUS_CHOICES = (
        ('SUGGESTED', 'AI 제안'),
        ('AUTO_APPROVED', '자동 승인'),  # ← 기본값 (병목 방지)
        ('APPROVED', '교수자 수동 승인'),
        ('MODIFIED', '교수자 수정'),
        ('REJECTED', '교수자 거부'),
    )

    live_session = FK(LiveSession, related_name='review_routes')
    student = FK(User, related_name='review_routes')
    items = JSONField()
    # [
    #   { "order": 1, "type": "note", "title": "오늘 통합 노트", "note_id": 5, "est_minutes": 10 },
    #   { "order": 2, "type": "concept", "title": "클로저 개념 복습", "content": "...", "est_minutes": 5 },
    #   { "order": 3, "type": "prev_session", "title": "지난주 스코프", "note_id": 3, "est_minutes": 8 },
    #   { "order": 4, "type": "preview", "title": "내일 Promise 선행", "content": "...", "est_minutes": 5 },
    # ]
    status = CharField(choices=STATUS_CHOICES, default='AUTO_APPROVED')
    total_est_minutes = IntegerField(default=0)
    completed_items = JSONField(default=list)  # [1, 2] = 완료된 order 목록
    created_at = DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['live_session', 'student']


class SpacedRepetitionItem(models.Model):
    """에빙하우스 5주기 간격 반복 스케줄"""
    student = FK(User, related_name='spaced_items')
    concept_name = CharField(max_length=200)
    source_session = FK(LiveSession, null=True, blank=True)
    source_quiz = FK(LiveQuiz, null=True, blank=True)
    review_question = TextField()
    review_answer = CharField(max_length=500)
    review_options = JSONField(default=list)  # 4지선다 보기
    # 5주기 암기법 (명세 기준)
    schedule = JSONField()
    # [
    #   { "review_num": 1, "label": "10분 후",  "due_at": "2026-02-20T15:10", "completed": false },
    #   { "review_num": 2, "label": "1일 후",   "due_at": "2026-02-21T15:00", "completed": false },
    #   { "review_num": 3, "label": "1주일 후", "due_at": "2026-02-27T15:00", "completed": false },
    #   { "review_num": 4, "label": "1개월 후", "due_at": "2026-03-20T15:00", "completed": false },
    #   { "review_num": 5, "label": "6개월 후", "due_at": "2026-08-20T15:00", "completed": false },
    # ]
    current_review = IntegerField(default=0)
    created_at = DateTimeField(auto_now_add=True)
```

### AI 복습 루트 생성 로직

```
[실행 시점] _generate_live_note() 완료 후 자동 (동일 스레드)

[입력]
  1. 오늘 오답 퀴즈·개념 (LiveQuizResponse.is_correct=False)
  2. 이전 세션 관련 개념 (STT 키워드 매칭)
  3. 학습자의 갭 맵 (StudentSkill) 중 status='GAP'인 항목
  4. 오늘 WeakZoneAlert 내역 (있으면)

[출력 — 복습 항목 순서]
  1순위: 오늘 통합 노트 열람 (무조건 첫 번째)
  2순위: 오답 개념 정리 (각 3~5분)
  3순위: 이전 강의 관련 개념 복습
  4순위: 다음 강의 선행 개념 미리보기

[SpacedRepetitionItem 자동 생성]
  각 오답 개념마다 1개 생성
  5주기: 10분 → 1일 → 1주 → 1개월 → 6개월
  review_question/answer는 GPT-4o-mini로 1문항 자동 생성

[승인 정책]
  기본값: AUTO_APPROVED (즉시 학생 전달)
  교수자가 "수동 승인 모드" 켜면: SUGGESTED (교수자 승인 대기)
```

### API 설계

| 메서드  | 경로                                 | 역할                  | 주체   |
| ------- | ------------------------------------ | --------------------- | ------ |
| `GET`   | `/review-routes/my/`                 | 내 복습 루트 목록     | 학습자 |
| `POST`  | `/review-routes/{id}/complete-item/` | 복습 항목 완료 체크   | 학습자 |
| `GET`   | `/review-routes/pending/`            | 승인 대기 루트        | 교수자 |
| `POST`  | `/review-routes/{id}/approve/`       | 루트 승인             | 교수자 |
| `PATCH` | `/review-routes/{id}/`               | 루트 수정             | 교수자 |
| `GET`   | `/spaced-repetition/due/`            | 오늘 복습 due 항목    | 학습자 |
| `POST`  | `/spaced-repetition/{id}/complete/`  | 복습 완료 (정답 체크) | 학습자 |

### 프론트엔드

**학습자 (LearningView.vue — 세션 종료 후)**

- "📚 오늘의 복습 루트" 카드 (교수자 승인 대기 시 안내 표시)
- 체크리스트: [ ] 통합 노트 (10분) → [ ] 클로저 복습 (5분)
- 상단: "총 예상 복습 시간: 28분"

**학습자 대시보드 (DashboardView.vue)**

- 상단 "오늘의 할 일" 섹션 바로 아래에 배치
- "🔔 복습 알림 N건" — 간격 반복 due 항목 카드
- "3일 전 배운 클로저, 기억하세요?" → [30초 퀴즈] 버튼

**교수자 (LectureDetailView.vue)**

- 세션 히스토리 또는 별도 탭에 복습 루트 관리
- 간략 리스트 + [승인/수정/거부]

### 예상 작업량: ~1시간 30분

---

## Phase 2-4. 형성평가 + 간격 반복 연계

### 개요

- 통합 노트 기반 사후 형성평가 3~5문항 자동 생성
- 오답 → 갭 맵 업데이트 + SpacedRepetitionItem 자동 등록

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

    live_session_note = FK(LiveSessionNote, related_name='formative_assessments')
    questions = JSONField()
    # [
    #   {
    #     "id": 1,
    #     "question": "클로저란 무엇인가?",
    #     "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
    #     "correct_answer": "B",
    #     "explanation": "설명...",
    #     "related_note_section": "## 핵심 내용 정리 > 1. 클로저",
    #     "concept_tag": "클로저",
    #   },
    # ]
    status = CharField(choices=STATUS_CHOICES, default='DRAFT')
    deadline_hours = IntegerField(default=24)
    created_at = DateTimeField(auto_now_add=True)
    approved_at = DateTimeField(null=True)


class FormativeResponse(models.Model):
    """학습자의 형성평가 응답"""
    assessment = FK(FormativeAssessment, related_name='responses')
    student = FK(User, related_name='formative_responses')
    answers = JSONField()  # { "1": "A", "2": "B", ... }
    score = IntegerField(default=0)
    total = IntegerField(default=0)
    wrong_concepts = JSONField(default=list)  # ["클로저", "스코프"]
    completed_at = DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['assessment', 'student']
```

### concept_tag → StudentSkill 매핑 로직 (보완)

```
형성평가 제출 시 오답 concept_tag 처리:

1. Skill.objects.filter(name__icontains=concept_tag) → 정확한 매칭 시도
2. 매칭 실패 시 → Skill 이름 전체 리스트를 GPT에 보내서 가장 유사한 Skill 선택
3. 매칭 성공 → StudentSkill.objects.filter(student=user, skill=matched_skill)
   - status='OWNED' → status='LEARNING', progress -20
   - status='LEARNING' → progress -10 (최소 0)
   - status='GAP' → 변화 없음 (이미 미보유)
4. SpacedRepetitionItem 생성 (5주기)
```

### 형성평가 → 간격 반복 연계 플로우

```
학습자 형성평가 제출 (POST /formative/{id}/submit/)
  ↓
채점 + wrong_concepts 추출
  ↓
각 오답 개념마다:
  1. concept_tag → Skill 매핑 (위 로직)
  2. StudentSkill 갭 맵 업데이트
  3. SpacedRepetitionItem 자동 생성 (5주기)
  ↓
응답 저장 (FormativeResponse)
  ↓
프론트: 결과 표시 + "📖 노트에서 확인" 바로가기 + 갭 맵 업데이트 안내
```

### API 설계

| 메서드  | 경로                       | 역할                                   | 주체   |
| ------- | -------------------------- | -------------------------------------- | ------ |
| `POST`  | `/formative/generate/`     | 노트 기반 형성평가 생성 (note_id 필요) | 교수자 |
| `GET`   | `/formative/{id}/`         | 형성평가 상세 조회                     | 교수자 |
| `PATCH` | `/formative/{id}/`         | 문항 수정                              | 교수자 |
| `POST`  | `/formative/{id}/approve/` | 승인 → 배포                            | 교수자 |
| `GET`   | `/formative/my-pending/`   | 내 미완료 형성평가 목록                | 학습자 |
| `POST`  | `/formative/{id}/submit/`  | 풀이 제출 + 자동 채점                  | 학습자 |
| `GET`   | `/formative/{id}/result/`  | 내 결과 + 오답 노트 연결               | 학습자 |

### 프론트엔드

**교수자 (LectureDetailView.vue)**

- 인사이트 리포트 하단: [📝 형성평가 생성] 버튼
- AI 초안 미리보기 → 문항별 수정 → [승인 & 배포]

**학습자 (LearningView.vue 또는 별도 뷰)**

- "📝 형성평가 N건 미완료" 배지
- [오늘 배운 내용 확인하기] → 3~5문항 풀이
- 결과: 정답/오답 + 해설 + "📖 노트에서 확인" 링크
- 결석생도 동일 접근 가능

**학습자 대시보드 (DashboardView.vue)**

- 간격 반복 알림: "🔔 3일 전 클로저, 기억하세요?" → [30초 퀴즈]

### 예상 작업량: ~1시간 30분

---

## 📊 구현 순서 + 예상 일정 (확정)

| 순서  | Step                     | 핵심 산출물                                | 예상 시간       |
| ----- | ------------------------ | ------------------------------------------ | --------------- |
| **0** | 전처리                   | PulseLog 모델 + lectureMaterials 버그 수정 | 10분            |
| **1** | 2-1 Weak Zone Alert      | WeakZoneAlert + 감지 로직 + 양쪽 UI        | 50분            |
| **2** | 2-3 AI Review + SR       | ReviewRoute + SpacedRepetitionItem + 5주기 | 1시간 30분      |
| **3** | 2-4 Formative Assessment | FormativeAssessment + Response + 갭맵 연동 | 1시간 30분      |
| **4** | 2-2 Adaptive Content     | AdaptiveContent + AI 변형                  | 1시간           |
|       |                          | **총 예상**                                | **~5시간 20분** |

### 구현 순서 근거

1. **전처리 필수**: PulseLog 없으면 2-1 감지 불가
2. **2-1 → 2-3**: Weak Zone 데이터가 복습 루트 우선순위에 직접 반영됨
3. **2-3 → 2-4**: SpacedRepetitionItem 모델을 2-3에서 만들고 2-4에서 재사용
4. **2-2 마지막**: 완전 독립적. PlacementResult.level만 있으면 동작

---

## 🗂️ 파일 변경 예상

### 백엔드

```
backend/learning/
├── models.py              # +5 모델 (PulseLog, WeakZone, AdaptiveContent, ReviewRoute, SR, Formative×2)
├── live_views.py          # pulse API 수정 (PulseLog 추가), answer_quiz 수정 (WeakZone 트리거)
├── weak_zone_views.py     # Phase 2-1 API (NEW)
├── adaptive_views.py      # Phase 2-2 API (NEW)
├── review_views.py        # Phase 2-3 API (NEW)
├── formative_views.py     # Phase 2-4 API (NEW)
├── urls.py                # URL 등록 추가
└── admin.py               # Admin 등록 추가
```

### 프론트엔드

```
frontend/src/views/
├── LearningView.vue       # Weak Zone 팝업 + 복습 루트 + 형성평가
├── DashboardView.vue      # 간격 반복 알림 + 형성평가 미완료 배지
└── ReviewRouteView.vue    # 복습 루트 전용 뷰 (NEW, 선택적)

Professor_dashboard/src/views/
├── LectureDetailView.vue  # Weak Zone 관리 + 적응형 콘텐츠 + 루트 승인 + 형성평가
```

---

## ⚠️ 리스크 및 대응

| 리스크                | 영향                                        | 대응                                              |
| --------------------- | ------------------------------------------- | ------------------------------------------------- |
| AI API 비용           | 변형 + 형성평가 + SR + WeakZone = 다수 호출 | 전부 `gpt-4o-mini` 사용                           |
| 간격 반복 cron        | 매일 알림 발송                              | 1차: 프론트 접속 시 due 체크 (폴링) / 2차: Celery |
| 교수자 승인 병목      | 복습 루트 N명 × M세션                       | 기본값=자동 승인, 교수자 선택 시 수동 전환        |
| 데이터 불충분         | 첫 세션은 AI 품질 저하                      | Fallback 기본 루트 + 안내 메시지                  |
| concept_tag 매핑 실패 | 형성평가 오답→갭 맵 연동 불가               | AI Fallback + 로그 (수동 확인용)                  |
| PDF/PPT 텍스트 추출   | 복잡한 레이아웃은 추출 실패                 | 1차: MD만 지원, 에러 안내                         |

---

## ✅ 체크리스트

### [전처리]

- [ ] `PulseLog` 모델 생성 + 마이그레이션
- [ ] pulse API에 PulseLog.create() 추가
- [ ] `LectureDetailView.vue`의 `lectureMaterials` → `materials` 수정 (3곳)

### Phase 2-1. Weak Zone Alert

- [ ] `WeakZoneAlert` 모델 생성
- [ ] answer_quiz 내 오답 감지 트리거 삽입
- [ ] pulse API 내 혼란 감지 트리거 삽입
- [ ] AI 보충 설명 자동 생성 (감지 시점)
- [ ] 교수자: Weak Zone 목록 + 푸시/거부 UI
- [ ] 학습자: Weak Zone 알림 팝업

### Phase 2-2. Adaptive Content Branching

- [ ] `AdaptiveContent` 모델 생성
- [ ] AI 교안 변형 API (MD 우선, PDF 2차)
- [ ] 교수자: 레벨별 미리보기 + 승인/수정/거부
- [ ] 학습자: 본인 레벨 자료 자동 표시 + 도전 토글

### Phase 2-3. AI Review Suggestion

- [ ] `ReviewRoute` + `SpacedRepetitionItem` 모델 생성
- [ ] 세션 종료 시 복습 루트 자동 생성 (AUTO_APPROVED 기본)
- [ ] 학습자: 복습 루트 체크리스트 + 진행률
- [ ] 교수자: 루트 관리 (수동 승인 모드 시)
- [ ] 간격 반복: 5주기 스케줄 생성 + due 조회 + 미니 퀴즈

### Phase 2-4. Formative Assessment

- [ ] `FormativeAssessment` + `FormativeResponse` 모델 생성
- [ ] AI 형성평가 자동 생성 (노트 기반 3~5문항)
- [ ] 교수자: 문항 검토 + 승인 & 배포
- [ ] 학습자: 풀이 + 결과 + 오답→노트 바로가기
- [ ] 오답 concept_tag → StudentSkill 매핑 + 갭 맵 업데이트
- [ ] 오답 → SpacedRepetitionItem 5주기 자동 등록
