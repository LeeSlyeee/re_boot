# 개발 작업 로그

## 1. 🔒 보안 및 인증 강화 (Authentication Enforcement)

**목표**: "누군지 몰라도 실행되면 안 된다"는 원칙에 따라 비로그인 사용자의 접근을 원천 차단.

- **Backend (`views.py`)**:
  - `LearningSessionViewSet`의 권한을 `[IsAuthenticated]`로 복구하여 로그인 필수화.
  - 익명 사용자에게 임의의 테스트 계정을 할당하던 'Fallback 로직' 전체 삭제.
  - 학습 세션 생성(`perform_create`), 기록 조회(`get_history`), 클래스 목록(`get_lecture_sessions`)에서 인증된 사용자만 데이터에 접근하도록 수정.

- **Frontend (`LearningView.vue`)**:
  - `401 Unauthorized` 에러 발생 시 즉시 **로그인 페이지로 리다이렉트** 처리.
  - 불필요한 `confirm()` 대화상자를 제거하여, 로그인 사용자는 끊김 없이 학습을 시작할 수 있도록 UX 개선.

## 2. 🎨 UI 디자인 대개편 (Glassmorphism)

**목표**: AI 튜터 챗봇과 어울리는 현대적이고 프리미엄한 '유리 질감' 디자인 적용.

- **스타일 시스템 (`main.scss`)**:
  - `.glass-panel`, `.glass-card` 클래스 고도화 (투명도 조절, 배경 흐림 `blur` 강화, 미세 테두리 적용).
  - 그림자(Shadow) 심도를 조절하여 입체감 부여.

- **컴포넌트 적용 (`LearningView.vue`)**:
  - **학습 모드 선택 화면**: 카드들에 반투명 유리 효과 적용.
  - **클래스 참여 모달**: 팝업창 전체에 글래스모피즘 테마 적용.
  - **학습 노트 & 채팅창**: 노트 작성 영역과 AI 튜터 대화창을 유리판 위에 떠 있는 듯한 디자인으로 변경.
  - **입력 폼**: 퀴즈 및 URL 입력창에도 일관된 디자인 언어 적용.

## 3. 🧠 AI 기능 고도화 (Noise Filtering)

**목표**: 물리적 공간(강의실)의 소음 및 잡담이 학습 노트에 섞이는 문제 해결.

- **프롬프트 엔지니어링 (`views.py`)**:
  - AI 요약 생성 로직(`_call_openai_summary`)에 강력한 **필터링 규칙** 추가.
  - **잡담 제거**: 농담, 주변 소음, 혼잣말 등 강의와 무관한 내용 삭제.
  - **화자 분리 효과**: 학생들의 단순 질문이나 웅성거림을 배제하고 '강의자(Instructor)'의 설명 위주로 요약.
  - **정제**: "음...", "저기..." 같은 무의미한 추임새 제거.

## 4. 🛠 시스템 및 유지보수

- **서버 안정화**:
  - OpenAI API 연동 코드의 문법 오류(`SyntaxError`) 수정 및 서버 정상 가동 확인.
  - 포트 충돌 문제 해결.
- **테스트 환경 재정비**:
  - `testuser` 계정의 비밀번호를 `testpass123`으로 초기화하여 테스트 접근성 확보.
- **Git 관리**:
  - `.gitignore` 파일을 생성하여 `.env`, `venv/`, `__pycache__` 등 불필요한 파일이 커밋되지 않도록 설정.

## 5. �� 실시간 STT 반응성 및 정확도 개선 (Final Polish)

- **Frontend (`api/audioRecorder.js`)**:
  - **AudioContext Silence Detection**: 기존 3초 강제 커팅 방식을 폐기하고, 아날라이저를 통해 **침묵(Silence < -50dB) 감지 시 커팅**하는 스마트 로직 도입.
  - **No Overlap (Gapless Seq)**: 말 자르기 방지 기술(Smart Cut) 덕분에 중복 녹음(Overlap)이 불필요해져 메아리/반복 현상 원천 차단.

- **Backend (`learning/views.py`)**:
  - **Whisper `verbose_json`**: `NoSpeechProb` 확률을 직접 조회하여, 침묵 확률이 50% 이상일 경우 자막 생성 스킵 (환각 원천 차단).
  - **Hallucination Blacklist**: 사용자 제보 환각 패턴("가죽팬티", "금메달" 제외, 기계적 안내문구 추가) 차단.
  - **Repeition/Echo Filter**: 내부 반복("안녕하세요 안녕하세요") 및 프롬프트 에코(이전 문맥 반복) 필터 추가.
  - **Prompt Context Repair**: `reversed()` 쿼리셋 오류 수정 및 문맥 유지(Prompting) 로직 안정화.

- **Frontend (`LearningView.vue`)**:
  - **UI/UX**: 실시간 처리 상태 인디케이터(`isProcessingAudio`) 및 **STT Debugger** 패널 추가로 투명성 확보.
