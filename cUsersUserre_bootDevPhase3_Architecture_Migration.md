
### 8.3. 트러블슈팅 및 기능 개선 (최신 업데이트)
1. **Windows 환경 콘다(Conda) 가상환경 실행 오류 수정**:
   - 기존 `conda activate kws` 명령어 인식 실패 문제를 해결하기 위해, `C:\ProgramData\anaconda3\condabin\conda.bat` 절대 경로를 사용하여 교수용 PC 마이크 클라이언트가 안정적으로 실행되도록 개선했습니다.
2. **마이크 클라이언트 중복 실행(Auto-Start) 버그 픽스**:
   - 기존에는 `rpi-status` API가 호출될 때마다 CMD 창이 뜨도록 구현되어 있어, STT 등 다른 동작 중에도 중복 실행되는 현상이 있었습니다.
   - 이를 해결하기 위해 프론트엔드(`LectureDetailView.vue`)에서 교수가 명시적으로 '연결 테스트' 버튼을 눌렀을 때만 `manual_launch: true` 플래그를 넘기도록 수정하여 불필요한 중복 팝업을 차단했습니다.
