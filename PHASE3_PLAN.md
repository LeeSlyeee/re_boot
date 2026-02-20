# Phase 3: 교수자 대시보드 (데이터 기반 교수자 역할) — 구현 계획서

> 작성일: 2026-02-20
> 전제: Phase 0 (라이브 인프라) + Phase 1 (수준 진단 + 갭 맵) + Phase 2 (강의 고도화) 완료

---

## 🔍 기존 코드베이스 검증 결과

### 이미 사용 가능한 데이터 소스 (Phase 0~2)

| 데이터         | 모델                                                      | 위치    | Phase 3 활용              |
| -------------- | --------------------------------------------------------- | ------- | ------------------------- |
| 학생 레벨      | `PlacementResult` (level: BEGINNER/INTERMEDIATE/ADVANCED) | Phase 1 | 3-1 레벨 분포             |
| 세션 출석      | `LiveParticipant` (is_active, joined_at)                  | Phase 0 | 3-1 출석률                |
| 퀴즈 정답      | `LiveQuizResponse` (is_correct, quiz\_\_live_session)     | Phase 0 | 3-1 위험군 + 3-2 취약구간 |
| 펄스 체크      | `PulseLog` (pulse_type, student, live_session)            | Phase 2 | 3-1 위험군                |
| 결석 노트 열람 | `LiveSessionNote` (is_public) + 열람 추적 필요 → **NEW**  | -       | 3-1 보충학습 파악         |
| 형성평가 응답  | `FormativeResponse` (score, total, answers)               | Phase 2 | 3-2 취약구간 통합         |
| Weak Zone      | `WeakZoneAlert` (trigger_type, status)                    | Phase 2 | 3-2 취약구간              |
| 복습 루트      | `ReviewRoute` (items, status, completed_items)            | Phase 2 | 3-3 AI 제안               |
| 적응형 콘텐츠  | `AdaptiveContent` (level, status)                         | Phase 2 | 3-3 AI 제안               |
| 간격 반복      | `SpacedRepetitionItem` (schedule, current_review)         | Phase 2 | 3-3 AI 제안               |
| 스킬/갭 맵     | `Skill`, `StudentSkill` (status, progress)                | Phase 1 | 3-4 재분류                |

### 교수자 대시보드 현황 (LectureDetailView.vue)

기존 탭: `monitor | attendance | quiz | recording | live | diagnostic`
→ Phase 3에서 **`analytics` 탭 1개** 추가 (4개 서브패널로 구성)

---

## 🏗️ 구현 구조

### 신규 모델: 2개

```python
class NoteViewLog(models.Model):
    """결석 노트 열람 추적"""
    note = FK(LiveSessionNote, related_name='view_logs')
    student = FK(User)
    viewed_at = DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['note', 'student']


class GroupMessage(models.Model):
    """그룹별 타겟 메시지"""
    LEVEL_CHOICES = ((0, '전체'), (1, 'Level 1'), (2, 'Level 2'), (3, 'Level 3'))

    lecture = FK(Lecture, related_name='group_messages')
    sender = FK(User)  # 교수자
    target_level = IntegerField(choices=LEVEL_CHOICES, default=0)  # 0 = 전체
    target_students = JSONField(default=list, help_text="특정 학생 ID 목록 (빈 배열이면 레벨 기준)")
    title = CharField(max_length=200)
    content = TextField()
    message_type = CharField(choices=(
        ('NOTICE', '공지'),
        ('TASK', '추가 과제'),
        ('FEEDBACK', '1:1 피드백 요청'),
        ('SUPPLEMENT', '보충 자료'),
    ), default='NOTICE')
    created_at = DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
```

### 수정 모델: 0개 (기존 모델 그대로 활용)

---

## Phase 3-1. 학습자 수준 현황판

### 백엔드 API

```
GET /api/learning/professor/{lecture_id}/analytics/overview/
```

응답 구조:

```json
{
  "level_distribution": { "BEGINNER": 8, "INTERMEDIATE": 15, "ADVANCED": 5 },
  "total_students": 28,
  "avg_attendance_rate": 87.5,
  "avg_quiz_accuracy": 72.3,
  "session_count": 6,
  "at_risk_students": [
    {
      "id": 1,
      "username": "학생1",
      "risk_reasons": ["연속 2회 결석", "최근 퀴즈 정답율 38%"],
      "level": "BEGINNER",
      "attendance_rate": 50.0,
      "quiz_accuracy": 38.0,
      "confused_pulse_rate": 65.0,
      "absent_note_viewed": true,
      "formative_completed": false
    }
  ],
  "students": [
    {
      "id": 1,
      "username": "학생1",
      "level": "BEGINNER",
      "attendance_rate": 50.0,
      "quiz_accuracy": 45.0,
      "formative_avg_score": 60,
      "pulse_confused_rate": 30,
      "note_view_count": 3
    }
  ]
}
```

위험군 기준:

1. 연속 2회 이상 결석 (LiveParticipant 미존재)
2. 최근 세션 퀴즈 정답률 50% 미만
3. 펄스 CONFUSED 비율 60% 이상
4. 형성평가 미완료

### 결석생 보충 학습 확인

- `LiveParticipant`에 해당 세션 미참여 학생 = 결석
- `NoteViewLog` 존재 → 노트 열람 여부
- `FormativeResponse` 존재 → 형성평가 완료 여부

### 위험군 메시지 발송

```
POST /api/learning/professor/{lecture_id}/send-message/
Body: { student_ids: [1,2,3], title: "...", content: "...", message_type: "FEEDBACK" }
```

### 프론트 (LectureDetailView.vue — analytics 탭)

- **레벨 분포 도넛 차트** (vue-chartjs Doughnut 재사용)
- **출석률/정답률 바 차트**
- **위험군 학습자 테이블** (빨간 배경 + 위험 사유 태그)
- **결석생 보충 현황** (노트 열람 ✅/❌ + 형성평가 ✅/❌)
- **📩 메시지 발송 모달**

---

## Phase 3-2. 취약 구간 인사이트

### 백엔드 API

```
GET /api/learning/professor/{lecture_id}/analytics/weak-insights/
```

응답:

```json
{
  "insights": [
    {
      "rank": 1,
      "concept": "클로저",
      "session_title": "3강: JavaScript 심화",
      "wrong_rate": 63.0,
      "source": "QUIZ+FORMATIVE",
      "quiz_wrong_count": 12,
      "formative_wrong_count": 8,
      "total_students": 28,
      "affected_students": ["학생1", "학생3", "학생7"],
      "related_material_id": 5,
      "weak_zone_count": 4
    }
  ],
  "session_comparison": [
    {
      "session_title": "1강",
      "understand_rate": 85,
      "quiz_accuracy": 78,
      "formative_avg": 72
    },
    {
      "session_title": "2강",
      "understand_rate": 72,
      "quiz_accuracy": 65,
      "formative_avg": 60
    }
  ]
}
```

로직:

1. `LiveQuizResponse` (is_correct=False) → 세션별/퀴즈별 오답 집계
2. `FormativeResponse.answers` (is_correct=False) → concept_tag별 오답 집계
3. 1+2 합산 → 오답률 높은 순 정렬 → 강의 개선 우선순위
4. `WeakZoneAlert` 트리거 빈도도 반영

### 프론트

- **취약 구간 랭킹 테이블** (순위 + 개념명 + 오답률 바 + 영향 학생 수)
- 각 행 클릭 → 해당 교안으로 이동 링크
- **차시별 비교 라인 차트** (이해도 + 퀴즈 정답률 + 형성평가 평균)

---

## Phase 3-3. AI 제안 승인 흐름

### 백엔드 API

```
GET /api/learning/professor/{lecture_id}/analytics/ai-suggestions/
```

응답:

```json
{
  "pending_suggestions": [
    {
      "type": "REVIEW_ROUTE",
      "id": 12,
      "student_name": "학생5",
      "detail": "3강 복습 루트 (3항목, 15분)",
      "created_at": "...",
      "actions": ["APPROVE", "MODIFY", "REJECT"]
    },
    {
      "type": "WEAK_ZONE_PUSH",
      "id": 8,
      "student_name": "학생2",
      "detail": "클로저 보충 설명",
      "actions": ["APPROVE", "REPLACE", "REJECT"]
    },
    {
      "type": "ADAPTIVE_CONTENT",
      "id": 3,
      "material_title": "3강 교안",
      "detail": "Level 1 변형 초안",
      "actions": ["APPROVE", "MODIFY", "REJECT"]
    }
  ],
  "recent_decisions": [
    { "type": "REVIEW_ROUTE", "action": "APPROVED", "decided_at": "..." }
  ]
}
```

로직:

- `ReviewRoute.status == 'SUGGESTED'` 수집
- `WeakZoneAlert.status == 'DETECTED'` 수집
- `AdaptiveContent.status == 'DRAFT'` 수집
- 통합하여 시간순 정렬

### 프론트

- **AI 제안 알림 카드 목록** (유형 아이콘 + 대상 학생 + 상세)
- 각 카드: [✅ 승인] [🔄 교체] [❌ 거부] 버튼
- **최근 판단 이력 목록** (교수자 투명성 확보)

---

## Phase 3-4. 그룹별 개입 도구 + 강의 품질 리포트

### 백엔드 API

```
POST /api/learning/professor/{lecture_id}/send-group-message/
Body: { target_level: 1, title: "Level 1 보충 안내", content: "...", message_type: "SUPPLEMENT" }
```

```
GET /api/learning/professor/{lecture_id}/analytics/quality-report/
```

응답:

```json
{
  "sessions": [
    {
      "id": 1,
      "title": "1강",
      "date": "2026-02-15",
      "metrics": {
        "understand_rate": 85.0,
        "participation_rate": 92.5,
        "quiz_accuracy": 78.0,
        "formative_completion_rate": 65.0,
        "weak_zone_count": 3,
        "avg_pulse_confused": 15.0
      }
    }
  ],
  "trends": {
    "understand_rate": [85, 72, 80, 88],
    "quiz_accuracy": [78, 65, 71, 82],
    "formative_completion": [65, 55, 70, 75]
  },
  "level_redistribution": {
    "current": { "BEGINNER": 8, "INTERMEDIATE": 15, "ADVANCED": 5 },
    "suggested": { "BEGINNER": 5, "INTERMEDIATE": 17, "ADVANCED": 6 },
    "changes": [
      {
        "student": "학생3",
        "from": "BEGINNER",
        "to": "INTERMEDIATE",
        "reason": "최근 3회 퀴즈 정답률 85%+"
      }
    ]
  }
}
```

### 학생 레벨 재분류 로직

```
자동 레벨 재분류 기준 (Phase 3-4):

승급 조건 (any):
  - 최근 3세션 퀴즈 정답률 >= 80%
  - 형성평가 점수 >= 80%
  - WeakZone 발생 0건
  - 펄스 이해 비율 >= 80%

강등 조건 (any):
  - 최근 3세션 퀴즈 정답률 <= 40%
  - 형성평가 점수 <= 40%
  - WeakZone 연속 3건 이상
  - 펄스 혼란 비율 >= 70%

→ 교수자에게 '제안'으로 표시, 교수자 승인 후 반영
→ PlacementResult 새 레코드 생성 (level 변경)
```

### 학생 메시지 수신 (학습자 프론트)

```
GET /api/learning/messages/my/
```

- 대시보드 상단에 알림 배지 + 메시지 목록 패널

### 프론트

- **그룹 메시지 발송 폼** (레벨 선택 드롭다운 + 내용 + 유형)
- **강의 품질 리포트 카드** (차시별 메트릭 테이블 + 추이 라인 차트)
- **레벨 재분류 제안 패널** (현재 → 제안 비교 + 일괄 승인/개별 승인)

---

## 📊 구현 순서 + 예상 일정

| 순서  | Step                        | 핵심 산출물                                               | 예상 시간       |
| ----- | --------------------------- | --------------------------------------------------------- | --------------- |
| **1** | 3-1 학습자 현황판           | NoteViewLog 모델 + overview API + 레벨 분포/위험군 UI     | 1시간           |
| **2** | 3-2 취약 구간 인사이트      | weak-insights API + 취약 랭킹 + 차시 비교 차트            | 50분            |
| **3** | 3-3 AI 제안 승인 흐름       | ai-suggestions API + 통합 승인 카드 UI                    | 40분            |
| **4** | 3-4 그룹 개입 + 품질 리포트 | GroupMessage 모델 + 품질 API + 재분류 제안 + 학생 수신 UI | 1시간 10분      |
|       |                             | **총 예상**                                               | **~3시간 40분** |

### 구현 순서 근거

1. 3-1이 기반 (overview API에서 학생 데이터 집계 → 이후 재사용)
2. 3-2는 3-1의 학생 데이터 + 퀴즈/형성평가 매핑
3. 3-3은 Phase 2 모델 상태(SUGGESTED/DRAFT/DETECTED)를 통합 조회
4. 3-4는 3-1~3의 데이터를 종합하여 리포트화 + 메시지 발송

---

## 🗂️ 파일 변경 예상

### 백엔드

```
backend/learning/
├── models.py              # +2 모델 (NoteViewLog, GroupMessage)
├── analytics_views.py     # NEW: Phase 3 전체 API (4개 GET + 2개 POST)
├── live_views.py          # 노트 조회 시 NoteViewLog 자동 기록 삽입
├── urls.py                # +6 URL 추가
└── admin.py               # +2 모델 등록
```

### 프론트엔드

```
Professor_dashboard/src/views/
└── LectureDetailView.vue  # analytics 탭 + 4개 서브패널 + 차트

frontend/src/views/
├── DashboardView.vue      # 메시지 알림 배지 + 목록
└── LearningView.vue       # 노트 조회 시 NoteViewLog 자동 기록
```

---

## ✅ 체크리스트

### Phase 3-1. 학습자 수준 현황판

- [ ] `NoteViewLog` 모델 생성 + 마이그레이션
- [ ] 학습자 노트 조회 시 NoteViewLog 자동 기록 (live_views.py 수정)
- [ ] `analytics/overview/` API 구현
- [ ] 교수자: analytics 탭 + 레벨 분포 도넛 차트
- [ ] 교수자: 위험군 학습자 테이블 + 결석생 보충 현황
- [ ] 교수자: 위험군 메시지 발송 모달 + API

### Phase 3-2. 취약 구간 인사이트

- [ ] `analytics/weak-insights/` API 구현 (퀴즈 + 형성평가 통합)
- [ ] 교수자: 취약 구간 랭킹 테이블 (오답률 바 + 교안 링크)
- [ ] 교수자: 차시별 비교 라인 차트

### Phase 3-3. AI 제안 승인 흐름

- [ ] `analytics/ai-suggestions/` API 구현 (3개 모델 통합)
- [ ] 교수자: AI 제안 카드 목록 + 승인/교체/거부 버튼
- [ ] 교수자: 최근 판단 이력

### Phase 3-4. 그룹별 개입 + 강의 품질 리포트

- [ ] `GroupMessage` 모델 생성 + 마이그레이션
- [ ] `send-group-message/` API (레벨별 + 개별)
- [ ] `analytics/quality-report/` API (차시별 메트릭 + 추이 + 재분류 제안)
- [ ] 학생 레벨 재분류 제안 + 교수자 승인 API
- [ ] 교수자: 그룹 메시지 발송 폼 + 품질 리포트 카드
- [ ] 교수자: 레벨 재분류 제안 패널
- [ ] 학습자: 대시보드 메시지 알림 + 목록
