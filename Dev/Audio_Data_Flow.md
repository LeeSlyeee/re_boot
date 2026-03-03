# 🎧 Re:Boot 실시간 오디오 데이터 플로우 (Phase 3 기반)

현재 아키텍처는 **자막/요약을 위한 STT(Speech-to-Text)**와 **키워드 검출을 위한 KWS(Keyword Spotting)**를 위해 마이크 입력이 두 갈래로 나뉘어 처리되는 하이브리드 스트리밍 구조를 띄고 있습니다.

## 오디오 파이프라인 아키텍처 다이어그램 (Flowchart)

```mermaid
flowchart TD
    classDef browser fill:#f9f9f9,stroke:#333,stroke-width:2px;
    classDef backend fill:#e3f2fd,stroke:#1565c0,stroke-width:2px;
    classDef edge fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px;
    classDef local fill:#fff3e0,stroke:#ef6c00,stroke-width:2px;

    subgraph "👨‍🏫 교수 PC (Professor / Local)"
        MIC["🎤 마이크 (Audio Input)"]
        
        subgraph "웹 브라우저 (Vue.js)"
            WEB_STT["Web Speech API<br>(STT 엔진)"]
        end
        
        subgraph "PC 오토 클라이언트 (Python CMD)"
            PC_VAD["client_pc_mic_VAD.py<br>(PyAudio + WebRTC VAD)"]
        end
    end

    subgraph "☁️ 백엔드 (Django Server)"
        API_STT["POST /api/learning/live/{id}/stt/<br>(텍스트 수신)"]
        API_WEBHOOK["POST /api/learning/live/kws-webhook/<br>(웹훅 수신)"]
        DB[("Event DB & 세션 상태")]
    end

    subgraph "🍓 엣지 디바이스 (Raspberry Pi 3 B+)"
        PI_SOCKET["server_pi_socket_VAD.py<br>(TCP 소켓 수신)"]
        MFCC["MFCC 특징 추출"]
        MODEL["DS-CNN KWS 모델 추론"]
        DETECTION{"키워드 감지 결과<br>('퀴즈', '이해했나요')"}
    end
    
    subgraph "👨‍🎓 학생 PC (Student Browser)"
        STUDENT_APP["Vue.js App<br>(상태 폴링)"]
        POPUP["UI 팝업<br>(퀴즈 풀이 / 이해도 펄스)"]
    end

    %% 오디오 입력 분할 분기
    MIC -->|"1. 브라우저 마이크 접근"| WEB_STT
    MIC -->|"1. 로컬 파이썬 마이크 캡처"| PC_VAD
    
    %% STT 흐름 (자막/노트용)
    WEB_STT -->|"2. 로컬 음성 인식 후 텍스트 전송 (HTTP)"| API_STT
    API_STT -->|"3. 자막 데이터베이스 저장"| DB
    
    %% KWS 오디오 스트리밍 흐름 (키워드 추출용)
    PC_VAD -->|"2. VAD 무음 제거 후 Raw Audio 스트리밍 (TCP Socket)"| PI_SOCKET
    PI_SOCKET -->|"3. 1초 단위 오디오 윈도우 버퍼링"| MFCC
    MFCC -->|"4. 전처리된 데이터 변환"| MODEL
    MODEL -->|"5. 80~90% 이상 신뢰도 일치 확인"| DETECTION
    
    %% KWS 감지 후 이벤트 흐름
    DETECTION -- "감지 완료" --> API_WEBHOOK
    API_WEBHOOK -->|"6. 즉각적인 웹훅 발동 (HTTP JSON)"| API_WEBHOOK
    API_WEBHOOK -->|"7. 퀴즈 생성 로직 트리거 및 이벤트 DB 저장"| DB
    
    %% 학생/교수 화면 피드백
    STUDENT_APP -->|"8. 1~3초 간격 상태 조회 폴링 (HTTP GET)"| DB
    DB -->|"9. 신규 KWS 이벤트 발송"| STUDENT_APP
    STUDENT_APP -->|"10. 화면에 모달/컴포넌트 렌더링"| POPUP

    class WEB_STT,STUDENT_APP,POPUP browser;
    class API_STT,API_WEBHOOK,DB backend;
    class PI_SOCKET,MFCC,MODEL,DETECTION edge;
    class MIC,PC_VAD local;
```

## 핵심 요약 (Key Takeaways)

1. **오디오 분리 처리**: 마이크 오디오는 웹 브라우저(STT용)와 로컬 모듈(KWS용)로 이중 캡처됩니다.
2. **트래픽 최적화**: 로컬 모듈의 VAD(Voice Activity Detection)가 침묵을 필터링하여 망 부하를 줄입니다.
3. **엣지 컴퓨팅**: 인퍼런스는 100% 라즈베리 파이 단말기에서 처리되며, 백엔드 서버에는 가벼운 텍스트 웹훅 신호 하나만 전송됩니다.
4. **리얼타임 동기화**: 백엔드에 이벤트가 등록되는 즉시, 모든 클라이언트 창의 다음 폴링 턴(수 초 이내)에 팝업 이벤트 트리거를 전송합니다.
