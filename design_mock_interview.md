# Re:Boot AI 모의 면접 (Mock Interview) 설계서

## 1. 개요 (Overview)

**Re:Boot Interview Coach**는 사용자가 생성한 **포트폴리오**와 **스킬 블록(Checklist)**을 분석하여, 실제 기술 면접과 가장 유사한 경험을 제공하는 AI 면접관 서비스입니다.

### 핵심 가치 (Core Value)

- **개인화 (Personalization)**: 정형화된 질문이 아닌, "내 프로젝트"와 "내 기술 스택"에 기반한 맞춤형 질문.
- **상호작용 (Interaction)**: 단답형 문답이 아닌, 꼬리 물기 질문(Follow-up Question)을 통한 깊이 있는 검증.
- **피드백 (Actionable Feedback)**: 면접 직후 답변의 논리적 허점과 개선 방향을 구체적으로 제시.

---

## 2. 사용자 시나리오 (User Flow)

1.  **면접 설정 (Setup)**:
    - 대상 포트폴리오 선택 (예: "2026-02-10 생성된 취업 포트폴리오").
    - 면접관 스타일 선택 (Tech Lead, HR Manager, Pressure Interviewer).
2.  **면접 진행 (Interview Session)**:
    - **Step 1**: AI 면접관이 첫 질문(자기소개 등)을 던짐.
    - **Step 2**: 사용자 답변 (텍스트 입력 or 음성 녹음).
      - _Tip_: 기존 STT 엔진(Whisper)을 활용해 음성 답변 지원 가능.
    - **Step 3**: AI가 답변 분석 후 **꼬리 질문** 생성 or **새로운 주제**로 전환.
      - (예: "상태 관리는 어떻게 하셨나요?" -> "Pinia를 썼습니다." -> "왜 Vuex 대신 Pinia를 선택했나요?")
    - **Step 4**: 5~10개의 질문-답변 사이클 반복.
3.  **결과 리포트 (Final Report)**:
    - 종합 점수 (기술적 깊이, 논리성, 태도).
    - **Best Answer**: 가장 잘 답변한 질문.
    - **Needs Improvement**: 답변이 부실했던 질문과 **모범 답안(Best Practice)** 예시 제공.

---

## 3. 데이터베이스 모델링 (ERD Draft)

### `MockInterview` (면접 세션)

- `id`: PK
- `student`: FK (User)
- `portfolio`: FK (Portfolio) - 어떤 포트폴리오 기반인지
- `persona`: Char (Choices)
  - **TECH_LEAD**: 깐깐한 기술 팀장 (기술 깊이, 아키텍처 검증)
  - **FRIENDLY_SENIOR**: 친절한 사수 (잠재력, 학습 태도, 협업)
  - **HR_MANAGER**: 인사 담당자 (컬처핏, 소프트 스킬)
  - **STARTUP_CEO**: 스타트업 대표 (비즈니스 임팩트, 문제 해결력)
  - **BIG_TECH**: 글로벌 빅테크 면접관 (CS 기초, 확장성, 시스템 설계)
  - **PRESSURE**: 압박 면접관 (논리적 허점 공격, 위기 대처)
- `status`: Char (IN_PROGRESS, COMPLETED)
- `created_at`: Datetime

### `InterviewExchange` (질문-답변 세트)

- `interview`: FK (MockInterview)
- `question_text`: Text (AI가 생성한 질문)
- `answer_text`: Text (사용자 답변)
- `feedback`: Text (이 답변에 대한 즉각적인 피드백/평가)
- `score`: Int (0~100)
- `order`: Int (질문 순서)

---

## 4. AI 프롬프트 설계 (System Prompt Strategy)

### Persona Definitions (면접관 스타일 정의)

1.  **깐깐한 기술 팀장 (TECH_LEAD)**
    - "당신은 10년차 시니어 개발자입니다. 지원자의 기술적 깊이를 집요하게 파고드세요. 'Why'에 집중하고, 대안 기술과의 비교를 요구하세요."
2.  **친절한 사수 (FRIENDLY_SENIOR)**
    - "당신은 지원자의 멘토가 될 수 있는 사람을 찾습니다. 편안한 분위기를 유도하되, 성장 가능성과 팀 적응력을 확인하는 질문을 하세요."
3.  **인사 담당자 (HR_MANAGER)**
    - "당신은 채용 담당자입니다. 기술보다는 지원자의 성격, 가치관, 갈등 해결 경험 등 소프트 스킬에 집중하세요."
4.  **스타트업 대표 (STARTUP_CEO)**
    - "당신은 초기 스타트업 창업자입니다. 기술적 완성도보다 '속도', '비즈니스 가치', '주도적인 문제 해결' 경험을 물어보세요."
5.  **글로벌 빅테크 (BIG_TECH)**
    - "당신은 구글/메타 스타일의 면접관입니다. CS 기초(자료구조/알고리즘) 원리와 대규모 트래픽 처리에 대한 이해도를 검증하세요."
6.  **압박 면접관 (PRESSURE)**
    - "당신은 지원자의 멘탈을 테스트하는 면접관입니다. 답변의 허점을 날카롭게 지적하고, 곤란한 상황을 가정하여 어떻게 대처하는지 확인하세요."

### Context Injection

```text
[Role]: {Selected_Persona_Prompt}
[Portfolio & Skills]: {portfolio_content} / {skills_block}

위 페르소나에 빙의하여 지원자에게 질문을 던지세요.
한 번에 하나의 질문만 하세요.
```

### Dynamic Questioning (동적 질문 생성)

- 사용자의 답변이 너무 짧으면 -> _"구체적인 사례를 들어 설명해주실 수 있나요?"_
- 사용자가 모른다고 하면 -> _"그렇다면 비슷한 다른 기술은 써보신 적 있나요?"_ (유도 질문)

---

## 5. 개발 로드맵 (Implementation Steps)

### Phase 3-1: Backend (API & Model)

- `career` 앱에 모델(`MockInterview`, `InterviewExchange`) 추가.
- `/api/career/interview/start/`: 세션 생성 및 첫 질문.
- `/api/career/interview/chat/`: 답변 제출 및 다음 질문 생성 (Streaming 고려).

### Phase 3-2: Frontend (Chat Interface)

- 카카오톡/ChatGPT 스타일의 대화형 UI 구현.
- **[녹음하기]** 버튼 추가 (기존 STT 기능 재사용).
- 실시간 타이핑 효과 (Loading Indicator).

### Phase 3-3: Report UI

- 면접 종료 후 "면접 결과표" 대시보드.
- 차트(Radar Chart)로 역량 시각화.
