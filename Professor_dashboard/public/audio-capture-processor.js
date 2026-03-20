/**
 * AudioWorklet Processor: 마이크 PCM 캡처 + VAD
 * ================================================
 * 브라우저 오디오 스레드에서 실행되며,
 * Float32 오디오 데이터를 Int16으로 변환하고
 * 250ms(4000 samples) 단위로 메인 스레드에 전달합니다.
 * 
 * VAD (Voice Activity Detection):
 *   - client_pc_mic_VAD.py의 WebRTC VAD와 동일한 역할
 *   - 250ms 청크의 RMS 에너지가 임계치 이상일 때만 실제 오디오 전송
 *   - 침묵/잡음 시 제로 패딩 데이터 전송 (Pi 슬라이딩 윈도우 유지용)
 * 
 * 오디오 스펙:
 *   - 입력: 브라우저 AudioContext (보통 48kHz)
 *   - 출력: 16kHz, Int16, 모노, 250ms = 8000 bytes
 */

class AudioCaptureProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        // 250ms @ 16kHz = 4000 samples
        this.TARGET_SAMPLE_RATE = 16000;
        this.CHUNK_SAMPLES = 4000; // 250ms 분량
        this.buffer = new Float32Array(this.CHUNK_SAMPLES);
        this.bufferOffset = 0;
        this.inputSampleRate = sampleRate; // AudioContext의 sampleRate (전역)
        this.resampleRatio = this.inputSampleRate / this.TARGET_SAMPLE_RATE;

        // VAD 설정 (client_pc_mic_VAD.py의 VAD_MODE=2 대응)
        // webrtcvad MODE 2 = 공격적 필터링 (확실한 음성만 통과)
        // 디버그: 침묵 시 RMS ≈ 0.01, 발화 시 RMS ≈ 0.03~0.1
        // 0.02 이상만 음성으로 판정 → 배경 소음 제거
        this.VAD_THRESHOLD = 0.02;
        // 제로 패딩 버퍼 (침묵 시 전송용, Pi의 슬라이딩 윈도우 유지)
        this.ZERO_BUFFER = new Int16Array(this.CHUNK_SAMPLES);
    }

    process(inputs, outputs, parameters) {
        const input = inputs[0];
        if (!input || input.length === 0) return true;

        const channelData = input[0]; // 모노 첫 번째 채널
        if (!channelData) return true;

        // 리샘플링: 브라우저 sampleRate → 16kHz (최근접 이웃)
        for (let i = 0; i < channelData.length; i++) {
            const targetIndex = Math.floor(i / this.resampleRatio);
            if (targetIndex !== Math.floor((i - 1) / this.resampleRatio) || i === 0) {
                const sample = channelData[i];
                if (this.bufferOffset < this.CHUNK_SAMPLES) {
                    this.buffer[this.bufferOffset++] = sample;
                }
            }
        }

        // 250ms 분량이 모이면 VAD 판정 후 메인 스레드로 전송
        if (this.bufferOffset >= this.CHUNK_SAMPLES) {
            // VAD: RMS 에너지 계산
            let sumSquares = 0;
            for (let i = 0; i < this.CHUNK_SAMPLES; i++) {
                sumSquares += this.buffer[i] * this.buffer[i];
            }
            const rms = Math.sqrt(sumSquares / this.CHUNK_SAMPLES);
            const isSpeech = rms > this.VAD_THRESHOLD;

            if (isSpeech) {
                // 음성 감지됨 → 게인 보상 후 Float32 → Int16 변환
                // 브라우저 마이크는 PyAudio보다 5~10배 낮은 볼륨으로 캡처됨
                // Pi의 과도한 정규화(x15 이상)를 방지하기 위해 미리 증폭
                const GAIN_FACTOR = 5.0;
                const int16Data = new Int16Array(this.CHUNK_SAMPLES);
                for (let i = 0; i < this.CHUNK_SAMPLES; i++) {
                    const amplified = this.buffer[i] * GAIN_FACTOR;
                    const s = Math.max(-1, Math.min(1, amplified)); // 클리핑
                    int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                }
                this.port.postMessage({
                    type: 'audio',
                    buffer: int16Data.buffer,
                    isSpeech: true,
                    rms: rms
                }, [int16Data.buffer]);
            } else {
                // 침묵/잡음 → 제로 패딩 전송 (Pi 슬라이딩 윈도우 유지)
                const zeroData = new Int16Array(this.CHUNK_SAMPLES); // 모두 0
                this.port.postMessage({
                    type: 'audio',
                    buffer: zeroData.buffer,
                    isSpeech: false,
                    rms: rms
                }, [zeroData.buffer]);
            }

            // 버퍼 초기화
            this.buffer = new Float32Array(this.CHUNK_SAMPLES);
            this.bufferOffset = 0;
        }

        return true; // 계속 처리
    }
}

registerProcessor('audio-capture-processor', AudioCaptureProcessor);
