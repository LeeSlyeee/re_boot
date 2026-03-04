"""
DS-CNN 기반 키워드 스포팅 엔진 (Keyword Spotting Engine)
강사 음성에서 교육 키워드를 실시간으로 감지

키워드 (6 클래스, TTS 모델):
  - quiz_start:  "퀴즈 시작"
  - quiz_solve:  "퀴즈 풀자"
  - problem:     "문제야"
  - understand:  "이해하셨나요"

듀얼 모드 지원:
  1) REMOTE: 라즈베리파이 소켓 서버로 오디오 전송 → 결과 수신
  2) LOCAL:  서버 내 TFLite 모델로 직접 추론 (라즈베리파이 미연결 시 폴백)

환경변수:
  KWS_RPI_HOST: 라즈베리파이 IP (기본: 172.16.206.43, 매번 변경 가능)
  KWS_RPI_PORT: 라즈베리파이 포트 (기본: 9999)
  KWS_MODE: 'remote' | 'local' | 'auto' (기본: auto)
    - auto: 라즈베리파이 연결 시도 → 실패 시 로컬 폴백
"""
import os
import socket
import logging
import threading
import numpy as np
import collections

logger = logging.getLogger(__name__)

# ── 파라미터 ──
SAMPLE_RATE = 16000
CLIP_DURATION_MS = 1000
WINDOW_SIZE_MS = 40
WINDOW_STRIDE_MS = 20
DCT_COEFFICIENT_COUNT = 10
FINGERPRINT_SIZE = 490  # 49 frames × 10 coefficients
CHUNK_SIZE = int(SAMPLE_RATE * 250 / 1000)  # 0.25초 = 4000 samples

# ── 라벨 (TTS 모델 6클래스) ──
LABELS = ['_silence_', '_unknown_', 'quiz_start', 'quiz_solve', 'problem', 'understand']

# ── 키워드 인덱스 (silence/unknown 제외) ──
KEYWORD_INDICES = [2, 3, 4, 5]

# ── 감지 임계값 ──
THRESHOLDS = {
    'quiz_start': 0.60,
    'quiz_solve': 0.60,
    'problem': 0.60,
    'understand': 0.60,
}
CONFIDENCE_GAP = 0.2  # 1위와 2위 클래스 간 최소 격차

# ── 안정성 파라미터 ──
SMOOTHING_WINDOW = 3        # 3연속 감지 필요
SUPPRESSION_TICKS = 10      # 감지 후 2.5초 중복 무시
MIN_VOLUME = 0.03           # 소음 기각

# ── 라즈베리파이 설정 (환경변수로 동적 관리) ──
RPI_HOST = os.environ.get('KWS_RPI_HOST', '172.16.206.43')
RPI_PORT = int(os.environ.get('KWS_RPI_PORT', '9999'))
KWS_MODE = os.environ.get('KWS_MODE', 'auto')  # remote | local | auto

# ── 라즈베리파이 트리거 → 내부 라벨 매핑 ──
TRIGGER_LABEL_MAP = {
    'TRIGGER_QUIZ_START': 'quiz_start',
    'TRIGGER_QUIZ_SOLVE': 'quiz_solve',
    'TRIGGER_PROBLEM': 'problem',
    'TRIGGER_UNDERSTAND': 'understand',
}

# ── 키워드 한글 표시명 ──
LABEL_DISPLAY = {
    'quiz_start': '🎯 퀴즈시작',
    'quiz_solve': '🧩 퀴즈풀자',
    'problem': '📝 문제야',
    'understand': '✅ 이해하셨나요',
}


class KWSEngine:
    """
    DS-CNN 키워드 스포팅 엔진 (싱글톤, 듀얼 모드)

    사용법:
        engine = KWSEngine.get_instance()
        result = engine.predict(audio_16k_float32)
    """
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """IP 변경 등으로 재초기화 필요 시"""
        with cls._lock:
            if cls._instance:
                cls._instance._disconnect_rpi()
            cls._instance = None

    def __init__(self):
        self._session_states = {}
        self._rpi_socket = None
        self._rpi_connected = False
        self._rpi_buffer = np.zeros(SAMPLE_RATE, dtype=np.float32)
        self._rpi_lock = threading.Lock()

        # 모드 결정
        self._mode = KWS_MODE  # 'remote', 'local', 'auto'

        # 로컬 TFLite 엔진 (auto/local 모드에서 사용)
        self._interpreter = None
        if self._mode in ('local', 'auto'):
            self._init_local_engine()

        # 라즈베리파이 연결 (auto/remote 모드에서 시도)
        if self._mode in ('remote', 'auto'):
            self._connect_rpi()

        active = 'RPI' if self._rpi_connected else 'LOCAL'
        logger.info(f"KWS Engine 초기화 완료 (모드: {self._mode}, 활성: {active})")

    # ════════════════════════════════════════
    #  로컬 TFLite 엔진
    # ════════════════════════════════════════

    def _init_local_engine(self):
        """
        로컬 TFLite 추론 — 현재 비활성화

        사유: DS-CNN 모델은 TF 1.x의 contrib_audio.audio_spectrogram + mfcc로
        학습되었으나, 로컬에서는 librosa.feature.mfcc를 사용하여 MFCC 특성이 불일치.
        이로 인해 모든 오디오에 높은 신뢰도로 오감지 발생 (과적합처럼 보이는 현상).

        라즈베리파이에서는 python_speech_features.mfcc를 사용하여 정상 동작.
        → 라즈베리파이 전용 모드로 운영 권장.
        """
        logger.info("로컬 TFLite 추론 비활성화 (MFCC 불일치 문제). 라즈베리파이 전용 모드.")

    def _extract_mfcc(self, audio_float32: np.ndarray) -> np.ndarray:
        import librosa
        n_fft = int(SAMPLE_RATE * WINDOW_SIZE_MS / 1000)
        hop_length = int(SAMPLE_RATE * WINDOW_STRIDE_MS / 1000)

        mfcc = librosa.feature.mfcc(
            y=audio_float32, sr=SAMPLE_RATE,
            n_mfcc=DCT_COEFFICIENT_COUNT,
            n_fft=n_fft, hop_length=hop_length, window='hann',
        )
        mfcc_t = mfcc.T
        target_frames = FINGERPRINT_SIZE // DCT_COEFFICIENT_COUNT
        if mfcc_t.shape[0] < target_frames:
            mfcc_t = np.vstack([mfcc_t, np.zeros((target_frames - mfcc_t.shape[0], DCT_COEFFICIENT_COUNT))])
        elif mfcc_t.shape[0] > target_frames:
            mfcc_t = mfcc_t[:target_frames]

        return mfcc_t.flatten().reshape(1, -1).astype(np.float32)

    def _predict_local(self, audio_float32: np.ndarray) -> np.ndarray:
        """로컬 TFLite 추론 → 확률 배열 [6]"""
        fingerprint = self._extract_mfcc(audio_float32)
        self._interpreter.set_tensor(self._input_details[0]['index'], fingerprint)
        self._interpreter.invoke()
        return self._interpreter.get_tensor(self._output_details[0]['index'])[0]

    # ════════════════════════════════════════
    #  라즈베리파이 원격 추론
    # ════════════════════════════════════════

    def _connect_rpi(self):
        """라즈베리파이 소켓 연결 시도"""
        host = os.environ.get('KWS_RPI_HOST', RPI_HOST)
        port = int(os.environ.get('KWS_RPI_PORT', str(RPI_PORT)))

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)  # 3초 타임아웃
            sock.connect((host, port))
            sock.settimeout(5)  # 이후 송수신 5초 타임아웃
            self._rpi_socket = sock
            self._rpi_connected = True
            self._rpi_recv_buffer = b''
            logger.info(f"🟢 라즈베리파이 연결 성공: {host}:{port}")
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            self._rpi_connected = False
            logger.warning(f"🔴 라즈베리파이 연결 실패 ({host}:{port}): {e}")
            if self._mode == 'remote':
                logger.error("remote 모드인데 라즈베리파이 연결 불가 — predict 호출 시 에러 발생")

    def _disconnect_rpi(self):
        if self._rpi_socket:
            try:
                self._rpi_socket.close()
            except Exception:
                pass
            self._rpi_socket = None
            self._rpi_connected = False

    def _predict_rpi(self, audio_float32: np.ndarray) -> dict:
        """
        라즈베리파이로 오디오 전송 → 결과 수신
        프로토콜: 0.25초 단위 Int16 청크 전송
        감지 시 "TRIGGER_QUIZ_START\n" / "TRIGGER_QUIZ_SOLVE\n" /
              "TRIGGER_PROBLEM\n" / "TRIGGER_UNDERSTAND\n" 수신
        """
        with self._rpi_lock:
            try:
                # 1초 오디오를 0.25초(4000 samples) 4개 청크로 분할 전송
                for i in range(0, SAMPLE_RATE, CHUNK_SIZE):
                    chunk = audio_float32[i:i + CHUNK_SIZE]
                    # Float32 → Int16 변환 (라즈베리파이 서버 프로토콜)
                    chunk_int16 = (chunk * 32768.0).astype(np.int16)
                    self._rpi_socket.sendall(chunk_int16.tobytes())

                # Non-blocking으로 응답 확인 (감지된 경우에만 데이터 옴)
                self._rpi_socket.setblocking(False)
                try:
                    data = self._rpi_socket.recv(256)
                    self._rpi_recv_buffer += data
                except BlockingIOError:
                    pass  # 데이터 없음 — 정상 (감지 안 됨)
                finally:
                    self._rpi_socket.setblocking(True)
                    self._rpi_socket.settimeout(5)

                # 버퍼에서 완성된 메시지 추출
                result = {'label': '_unknown_', 'confidence': 0.0, 'detected': False}
                while b'\n' in self._rpi_recv_buffer:
                    line, self._rpi_recv_buffer = self._rpi_recv_buffer.split(b'\n', 1)
                    msg = line.decode('utf-8').strip()
                    if msg in TRIGGER_LABEL_MAP:
                        label = TRIGGER_LABEL_MAP[msg]
                        display = LABEL_DISPLAY.get(label, label)
                        result = {'label': label, 'confidence': 1.0, 'detected': True}
                        logger.info(f"🔔 라즈베리파이 감지: {display}")

                return result

            except (BrokenPipeError, ConnectionResetError, OSError) as e:
                logger.warning(f"라즈베리파이 연결 끊김: {e}, 로컬 폴백 전환")
                self._rpi_connected = False
                self._disconnect_rpi()
                return None  # 폴백 신호

    def _post_filter_rpi(self, result: dict, session_id: int, volume: float) -> dict:
        """
        라즈베리파이 트리거에 후처리 필터 적용
        - 볼륨 게이트: 너무 작은 소리는 무시
        - 연속 감지: 같은 키워드가 2회 연속 감지되어야 인정
        - 억제: 감지 후 쿨다운
        """
        if not result['detected']:
            return result

        # 볼륨 게이트
        if volume < MIN_VOLUME:
            result['detected'] = False
            result['label'] = '_silence_'
            return result

        # 세션별 연속 감지 카운터
        if session_id is not None:
            if session_id not in self._session_states:
                self._session_states[session_id] = {
                    'history': collections.deque(maxlen=SMOOTHING_WINDOW),
                    'suppression': 0,
                    'rpi_streak': 0,
                    'rpi_last_label': None,
                }
            state = self._session_states[session_id]

            # 억제 중
            if state['suppression'] > 0:
                state['suppression'] -= 1
                return {'label': '_suppressed_', 'confidence': 0.0,
                        'detected': False, 'volume': volume, 'source': 'rpi'}

            # 연속 감지 체크 (같은 키워드 2회 연속)
            if result['label'] == state.get('rpi_last_label'):
                state['rpi_streak'] += 1
            else:
                state['rpi_streak'] = 1
            state['rpi_last_label'] = result['label']

            if state['rpi_streak'] < 2:
                # 아직 1회만 — 보류
                result['detected'] = False
                return result

            # 통과! 억제 카운터 설정
            state['suppression'] = SUPPRESSION_TICKS
            state['rpi_streak'] = 0

        return result

    # ════════════════════════════════════════
    #  통합 predict
    # ════════════════════════════════════════

    def predict(self, audio_float32: np.ndarray, session_id: int = None) -> dict:
        # 입력 정규화
        if len(audio_float32) < SAMPLE_RATE:
            padded = np.zeros(SAMPLE_RATE, dtype=np.float32)
            padded[:len(audio_float32)] = audio_float32
            audio_float32 = padded
        elif len(audio_float32) > SAMPLE_RATE:
            audio_float32 = audio_float32[:SAMPLE_RATE]

        volume = float(np.max(np.abs(audio_float32)))
        if volume < MIN_VOLUME:
            return {'label': '_silence_', 'confidence': 1.0, 'detected': False, 'volume': volume}

        # ── 라즈베리파이 원격 추론 시도 ──
        if self._rpi_connected:
            rpi_result = self._predict_rpi(audio_float32)
            if rpi_result is not None:
                rpi_result['volume'] = round(volume, 4)
                rpi_result['source'] = 'rpi'
                # 후처리 필터
                rpi_result = self._post_filter_rpi(rpi_result, session_id, volume)
                return rpi_result
            # None이면 연결 끊김 → 로컬 폴백

        # ── 로컬 TFLite 추론 ──
        if self._interpreter is None:
            return {'label': '_error_', 'confidence': 0.0, 'detected': False,
                    'volume': volume, 'error': '로컬 엔진 없음, 라즈베리파이 미연결'}

        probs = self._predict_local(audio_float32)

        # 스무딩 (세션별)
        if session_id is not None:
            if session_id not in self._session_states:
                self._session_states[session_id] = {
                    'history': collections.deque(maxlen=SMOOTHING_WINDOW),
                    'suppression': 0,
                }
            state = self._session_states[session_id]
            state['history'].append(probs)

            if state['suppression'] > 0:
                state['suppression'] -= 1
                return {'label': '_suppressed_', 'confidence': 0.0,
                        'detected': False, 'volume': volume, 'source': 'local'}

            if len(state['history']) >= SMOOTHING_WINDOW:
                probs = np.mean(state['history'], axis=0)

        top_idx = int(np.argmax(probs))
        label = LABELS[top_idx]
        confidence = float(probs[top_idx])

        # 차등 점수: 1위와 2위의 격차가 충분한지 확인
        sorted_probs = sorted(probs, reverse=True)
        gap = sorted_probs[0] - sorted_probs[1] if len(sorted_probs) > 1 else 1.0

        detected = False
        if (label in THRESHOLDS
                and confidence >= THRESHOLDS[label]
                and gap >= CONFIDENCE_GAP):
            detected = True
            if session_id is not None and session_id in self._session_states:
                self._session_states[session_id]['suppression'] = SUPPRESSION_TICKS

        return {
            'label': label,
            'confidence': round(confidence, 4),
            'detected': detected,
            'gap': round(gap, 4),
            'volume': round(volume, 4),
            'source': 'local',
        }

    def cleanup_session(self, session_id: int):
        self._session_states.pop(session_id, None)

    def get_status(self) -> dict:
        """현재 엔진 상태 조회"""
        return {
            'mode': self._mode,
            'rpi_connected': self._rpi_connected,
            'rpi_host': os.environ.get('KWS_RPI_HOST', RPI_HOST),
            'rpi_port': int(os.environ.get('KWS_RPI_PORT', str(RPI_PORT))),
            'local_available': self._interpreter is not None,
            'labels': LABELS,
            'keyword_labels': [LABELS[i] for i in KEYWORD_INDICES],
        }

    def reconnect_rpi(self, host: str = None, port: int = None):
        """라즈베리파이 IP 변경 시 재연결"""
        if host:
            os.environ['KWS_RPI_HOST'] = host
        if port:
            os.environ['KWS_RPI_PORT'] = str(port)
        self._disconnect_rpi()
        self._connect_rpi()
        return self.get_status()
