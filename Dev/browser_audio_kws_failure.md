# 🔬 브라우저 마이크 캡처(Web Audio API) KWS 인식 실패 분석

> **결론: 브라우저 Web Audio API로 캡처한 오디오는 DS-CNN 모델에서 QUIZ 키워드를 인식하지 못함**

## 배경

OCI 이전 후 교수 PC에 별도 프로그램 설치 없이 **브라우저만으로** 마이크→라즈베리파이 오디오 전달을 시도.

### 구현한 파이프라인

```
브라우저 AudioWorklet → WebSocket → OCI 중계서버(audio_relay.py) → TCP 소켓 → Raspberry Pi
```

### 오디오 스펙 (PyAudio와 동일하게 맞춤)
- 16kHz, Int16, 모노, 250ms(8000 bytes) 청크 ✅
- AudioContext.sampleRate = 16000 확인 ✅
- echoCancellation, noiseSuppression, autoGainControl 모두 비활성화 ✅
- 게인 보상 적용 (GAIN_FACTOR=5.0) → Pi 도달 볼륨 0.3~0.7 범위 ✅

## 실패 원인

### Pi 모델 추론 로그 비교

**PyAudio (정상 동작)**:
```
quiz: 85.2%, _unknown_: 14.8% → TRIGGER_QUIZ 발동
```

**브라우저 AudioWorklet (실패)**:
```
_unknown_: 100.0%, quiz: 0.0% → 인식 불가
```

### 근본적 차이

```
PyAudio:    마이크 → Windows 오디오 드라이버 → 직접 PCM 16kHz 캡처 (원본)
브라우저:   마이크 → Windows → 브라우저 내부 리샘플러(48kHz→16kHz) → MediaStream → PCM (가공됨)
```

브라우저의 내부 리샘플러(48kHz→16kHz 변환)가 주파수 특성을 미세하게 변형시키며,
이로 인해 MFCC 변환 결과가 달라져 DS-CNN 모델이 키워드를 인식하지 못함.

- `echoCancellation: false` 등 옵션으로도 **내부 리샘플러는 비활성화 불가**
- UNDERSTAND는 간헐적으로 감지되었으나 QUIZ는 전혀 감지되지 않음
- 모델이 학습된 오디오 특성(PyAudio 원본)과 브라우저 오디오 특성의 차이가 원인

## 시도한 해결 방법 및 결과

| 시도 | 결과 |
|---|---|
| echoCancellation/noiseSuppression/AGC 비활성화 | ❌ 효과 없음 |
| 게인 보상 (5배 증폭) | ❌ 볼륨은 정상화되었으나 인식 불가 |
| VAD 임계치 조정 (0.005→0.02) | ✅ VAD는 정상 동작하나 인식은 불가 |

## 대안 비교

| 방안 | 설치 | 구현 | 상태 |
|---|---|---|---|
| PyInstaller .exe 패키징 | .exe 더블클릭 | 중간 | **채택** |
| 브라우저 오디오 + 모델 재학습 | 없음 | 높음 | 보류 |
| kws_agent.py + conda 환경 | Python 필요 | 이미 완료 | 대체됨 |
