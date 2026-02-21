flowchart TD
    %% Phase 1: 진단 (수업 전 1회)
    subgraph Phase1 [Phase 1: 수준 진단 및 갭 맵]
        A[회원 가입 및 입학 진단 퀴즈] --> B[목표 설정]
        B --> C[초기 실력 갭 맵 Gap Map 생성]
    end

    %% Phase 0: 라이브 세션 (수업 중)
    subgraph Phase0 [Phase 0: 라이브 세션 인프라]
        D[교수자: 세션 생성] --> E[학습자: 세션 입장]
        E --> F{수업 중 상호작용}
        F --> |이해도 확인| G[실시간 펄스 체크]
        F --> |즉석 퀴즈 발동| H[키워드 감지 & Short-term STT]
        F --> |질문| I[익명 Q&A 큐]
        G & H & I --> J[교수자: 수업 종료]
    end

    %% Phase 0-6 & Phase 2: 사후 학습 (수업 직후)
    subgraph PostSession [Phase 0-6 & Phase 2: AI 후처리 및 복습]
        K[Batch STT & LLM 텍스트 요약] --> L[사전 교안 병합 및 교수자 승인]
        L --> M[디지털 요약 노트 배포]
        M --> N[AI 후속 형성평가 및 복습 제안]
        N -.오답 및 학습 데이터.-> O[개인 갭 맵 업데이트 & 간격 반복 스케줄]
    end

    %% Phase 3: 교수자 대시보드 (데이터 종합)
    subgraph Phase3 [Phase 3: 교수자 대시보드]
        P[학습자 위험군 식별]
        Q[다수 오답 취약 구간 분석]
        R[AI 복습 제안 교수자 최종 승인]
    end

    Phase1 --> D
    J --> K
    O -.전체 누적 데이터.-> Phase3
    Phase3 -.분석 인사이트.-> D
