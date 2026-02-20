# 🎓 Re:Boot 라이브 세션 인프라 구현 계획서

**생성일**: 2026-02-20  
**상태**: 검증 완료 → 구현 대기  
**검증일**: 2026-02-20

---

## 📐 아키텍처 결정

### 실시간 통신 방식: **Short Polling (5초 간격)**

| 방식                        | 장점                               | 단점                                            | 채택 여부   |
| --------------------------- | ---------------------------------- | ----------------------------------------------- | ----------- |
| WebSocket (Django Channels) | 진짜 실시간                        | Redis/Daphne 별도 인프라 필요, 배포 복잡도 증가 | ❌          |
| Server-Sent Events          | 서버→클라 단방향 실시간            | 양방향 불가, 브라우저 호환성                    | ❌          |
| **Short Polling (5s)**      | **인프라 변경 0, 기존 DRF 그대로** | 5초 지연 허용 필요                              | **✅ 채택** |

**이유**: 부트캠프 20~30명 규모에서는 5초 폴링으로 충분. 인프라 투자 없이 기존 Django REST Framework만으로 구현 가능.

---

## 🗂 구현 단계 (의존성 순서)

### 📦 Step 1: 라이브 세션 모델 + 교수자 세션 관리 (기반 공사)

**체크리스트 항목:**

- [ ] 교수자: 세션 생성 + QR코드 / 6자리 코드 발급
- [ ] 학습자: QR스캔 또는 코드 입력으로 세션 입장
- [ ] [NEW] 교수자: 강의 전 교안 업로드 (PDF / PPT / 마크다운) ← _Step 5에서 이동_

**백엔드 작업:**

1. `LiveSession` 모델 생성
   - `lecture` (FK → Lecture)
   - `instructor` (FK → User)
   - `session_code` (6자리 랜덤, 유니크)
   - `status` (WAITING / LIVE / ENDED)
   - `started_at`, `ended_at`
   - `title` (선택, "Week 3 - Django ORM")

2. `LiveParticipant` 모델 생성
   - `live_session` (FK → LiveSession)
   - `student` (FK → User)
   - `learning_session` (FK → LearningSession, null=True) ← _입장 시 자동 생성되는 개인 세션_
   - `joined_at`
   - `is_active` (True/False, heartbeat 기반)

3. `LectureMaterial` 모델 생성 ← _Step 5에서 이동_
   - `lecture` (FK → Lecture)
   - `file` (FileField, upload_to='materials/%Y/%m/')
   - `file_type` (PDF / PPT / MD)
   - `title` (CharField)
   - `uploaded_by` (FK → User)
   - `uploaded_at` (auto_now_add)

4. API 엔드포인트
   - `POST /api/learning/live/create/` → 세션 생성 + 코드 발급
   - `POST /api/learning/live/join/` → 학생 입장 (코드 입력), 개인 LearningSession 자동 생성
   - `GET /api/learning/live/{id}/status/` → 세션 상태 조회 (참가자 수 포함)
   - `POST /api/learning/live/{id}/end/` → 세션 종료
   - `POST /api/learning/lectures/{id}/materials/` → 교안 업로드
   - `GET /api/learning/lectures/{id}/materials/` → 교안 목록 조회

5. **모델 관계 설계:**

   ```
   LiveSession (1) ──▶ (N) LiveParticipant ──▶ (1) LearningSession (학생 개인)
       │                                              │
       └── STT는 교수자 마이크 기준 (LiveSession에 연결)     └── 학생별 펄스/퀴즈 응답 기록
   ```

   - STT 로그: 교수자 마이크 → `LiveSession`에 연결되는 별도 `LiveSTTLog` 모델
   - 학생 개인 활동(펄스/퀴즈 응답): `LiveParticipant` 또는 `LearningSession`에 연결

**프론트엔드 작업:**

- 교수자 대시보드: "라이브 세션 시작" 버튼 + 코드 표시 카드 + 교안 업로드 영역
- 학습자: 코드 입력 → 라이브 세션 입장 화면

---

### 📦 Step 2: 실시간 이해도 펄스 + 모니터링

**체크리스트 항목:**

- [ ] 학습자: 실시간 이해도 펄스 체크 버튼 (✅ / ❓)
- [ ] 교수자: 실시간 이해도 비율 확인 화면

**백엔드 작업:**

1. `PulseCheck` 모델 생성
   - `live_session` (FK → LiveSession)
   - `student` (FK → User)
   - `pulse_type` (UNDERSTAND / CONFUSED)
   - `created_at`

2. API 엔드포인트
   - `POST /api/learning/live/{id}/pulse/` → 학생 펄스 전송
   - `GET /api/learning/live/{id}/pulse-stats/` → 교수자 실시간 비율 조회

**프론트엔드 작업:**

- 학습자: 화면 하단 고정 ✅/❓ 플로팅 버튼
- 교수자: 실시간 이해도 게이지 바 (5초 폴링)

---

### 📦 Step 3: 체크포인트 퀴즈 (교수자 발동 → 학습자 수신)

**체크리스트 항목:**

- [ ] 교수자: STT 키워드 스팟팅 기반 트리거 감지
- [ ] 교수자: Short-term STT → AI 퀴즈 자동 생성 → 스마트 팝업
- [ ] 교수자: 체크포인트 퀴즈 발동 버튼 (AI 생성 확인 / 직접 입력 병행)
- [ ] 학습자: 퀴즈 팝업 수신 + 응답 + 즉시 정오답 확인

**백엔드 작업:**

1. `LiveQuiz` 모델 생성
   - `live_session` (FK → LiveSession)
   - `question_text`, `options` (JSON), `correct_answer`
   - `is_ai_generated` (Boolean)
   - `triggered_at`
   - `explanation` (TextField, 해설)

2. `LiveQuizResponse` 모델 생성
   - `quiz` (FK → LiveQuiz)
   - `student` (FK → User)
   - `answer`, `is_correct`
   - `responded_at`

3. **STT 키워드 스팟팅 구현 사양:**
   - **감지 주체**: 백엔드 (STT 텍스트 후처리)
   - **트리거 키워드 목록**: `["이해되셨나요", "질문 있나요", "여기까지 괜찮으시죠", "다음으로 넘어갈게요"]`
   - **감지 로직**: 최근 N개 STT 청크에서 키워드 매칭 → 교수자에게 "퀴즈 제안" 알림
   - **동작**: 자동 발동 아님, 교수자에게 **제안만** ("이 시점에 퀴즈를 내보시겠습니까?")
   - **AI 퀴즈 생성**: 기존 `_generate_quiz_from_ai()` 로직 재활용. 최근 5~10분 STT 텍스트 기반

4. API 엔드포인트
   - `POST /api/learning/live/{id}/quiz/create/` → 교수자가 퀴즈 발동
   - `POST /api/learning/live/{id}/quiz/generate/` → AI 퀴즈 자동 생성
   - `GET /api/learning/live/{id}/quiz/pending/` → 학생 미응답 퀴즈 조회
   - `POST /api/learning/live/{id}/quiz/{qid}/answer/` → 학생 응답
   - `GET /api/learning/live/{id}/quiz/{qid}/results/` → 교수자 결과 확인

**프론트엔드 작업:**

- 교수자: "퀴즈 발동" 버튼 + AI 생성/직접 입력 선택 모달
- 학습자: 퀴즈 팝업 (5초 폴링으로 신규 퀴즈 감지) + 즉시 채점

---

### 📦 Step 4: 익명 Q&A

**체크리스트 항목:**

- [ ] 학습자: 익명 질문 텍스트 입력 + 전송
- [ ] 교수자: 질문 큐 확인 + 유사 질문 묶음 처리

**백엔드 작업:**

1. `LiveQuestion` 모델 생성
   - `live_session` (FK → LiveSession)
   - `student` (FK → User, 서버에만 저장, 응답에 미포함)
   - `question_text`
   - `is_answered` (Boolean)
   - `cluster_group` (Integer, 유사 질문 묶음용)
   - `upvote_count` (Integer)
   - `created_at`

2. API 엔드포인트
   - `POST /api/learning/live/{id}/questions/` → 질문 전송
   - `GET /api/learning/live/{id}/questions/` → 질문 목록 (교수자용)
   - `POST /api/learning/live/{id}/questions/{qid}/upvote/` → 같은 질문 투표
   - `POST /api/learning/live/{id}/questions/cluster/` → AI 유사 질문 묶음

**프론트엔드 작업:**

- 학습자: 질문 입력 폼 + 다른 학생 질문 보기 + 공감 버튼
- 교수자: 질문 큐 패널 (실시간 갱신, 유사 질문 묶음 표시)

---

### 📦 Step 5: 세션 종료 + 배치 처리 + 교안 통합

**체크리스트 항목:**

- [ ] 교수자: 세션 종료 + 배치 STT 전사 + 인사이트 리포트
- [ ] 학습자: 세션 종료 후 개인 요약 + 갭 맵 업데이트
- [ ] 시스템: 배치 전사 완료 후 LLM 요약 + 교안 통합 (10~20분)
- [ ] 교수자: AI 통합 요약 노트 초안 검토 + 수정 + 배포 승인
- [ ] 학습자: 통합 요약 노트 수신 + 열람
- [ ] 학습자(결석생): 요약 노트 수신 + 셀프 테스트 + 갭 맵 반영
- [ ] (선택) 보이스 Q&A

**백엔드 작업:**

1. `IntegratedNote` 모델 (통합 요약 노트)
   - `live_session` (FK → LiveSession)
   - `content_text` (TextField)
   - `is_approved` (Boolean, 교수자 승인 여부)
   - `approved_at` (DateTimeField)
   - `material` (FK → LectureMaterial, null=True, 연결된 교안)

2. 세션 종료 시:
   - 기존 `recording_pipeline.py`의 배치 STT 재활용
   - 교안 + STT 전사본 → GPT-4o 통합 요약
   - `IntegratedNote` 생성 (초안)
   - 교수자 승인 후 학생 배포

---

## 🚦 현재 진행 상태

| Step       | 설명                                  | 상태    |
| ---------- | ------------------------------------- | ------- |
| **Step 1** | 라이브 세션 모델 + 입장 + 교안 업로드 | ⬜ 대기 |
| Step 2     | 이해도 펄스                           | ⬜ 대기 |
| Step 3     | 체크포인트 퀴즈                       | ⬜ 대기 |
| Step 4     | 익명 Q&A                              | ⬜ 대기 |
| Step 5     | 세션 종료 + 교안 통합                 | ⬜ 대기 |

---

## ⏱ 예상 소요 시간

| Step      | 백엔드 | 프론트엔드 | 합계            |
| --------- | ------ | ---------- | --------------- |
| Step 1    | ~40분  | ~40분      | ~1시간 20분     |
| Step 2    | ~20분  | ~20분      | ~40분           |
| Step 3    | ~40분  | ~40분      | ~1시간 20분     |
| Step 4    | ~30분  | ~30분      | ~1시간          |
| Step 5    | ~50분  | ~40분      | ~1시간 30분     |
| **Total** |        |            | **~5시간 30분** |
