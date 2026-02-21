# Re:Boot 로컬 파일 복구 가이드

이 가이드는 `git pull` 또는 새로운 환경에서 저장소를 클론한 후, Git에서 무시되었던 로컬 설정 및 환경 변수 파일들을 복구하는 방법을 안내합니다.

## 📁 백업 파일 구조
복구 대상 파일들은 `Dev/Backup` 폴더에 다음과 같이 정리되어 있습니다.

```text
Dev/Backup/
├── backend/
│   ├── .env              # 백엔드 환경 변수 설정
│   └── debug_stt.log     # STT 디버깅 로그
└── root_logs/            # 루트 디렉토리에 위치했던 실행 로그들
    ├── backend_stderr.log
    ├── frontend_stdout.log
    ├── professor_stderr.log
    └── professor_stdout.log
```

## 🛠️ 복구 방법

### 1. 명령어를 통한 자동 복구 (추천)
Bash 터미널(Git Bash 등)에서 다음 명령어를 실행하여 모든 파일을 제자리로 복사할 수 있습니다.

```bash
# 환경 변수 파일 복구
cp Dev/Backup/backend/.env backend/.env
cp Dev/Backup/backend/debug_stt.log backend/debug_stt.log

# 로그 파일들 복구
cp Dev/Backup/root_logs/*.log ./
```

### 2. 수동 복구 (복사 & 붙여넣기)
명령어 사용이 어려운 경우, 아래 경로에 맞춰 파일을 직접 복사하여 붙여넣으세요.

1. `Dev/Backup/backend/.env` 파일을 `backend/` 폴더 안으로 복사합니다.
2. `Dev/Backup/root_logs/` 내의 모든 `.log` 파일들을 프로젝트 **최상위 루트(Root)** 폴더로 복사합니다.

---

> [!IMPORTANT]
> - `.env` 파일에는 보안 정보나 API 키가 포함되어 있을 수 있으니 외부로 유출되지 않도록 주의하십시오.
> - 복구 후 서버가 정상적으로 작동하지 않는다면 각 `.env` 파일 내의 경로 설정을 점검하십시오.
