export class AudioRecorder {
    constructor(onDataAvailable, onError = null) {
        this.onDataAvailable = onDataAvailable;
        this.onError = onError;  // 외부 에러 핸들러 (alert 대체)
        this.stream = null;
        this.audioStream = null;
        this.isRecording = false;
        this.interval = 3000;
        this.currentRecorder = null;
        this._consecutiveErrors = 0;   // 연속 에러 카운터
        this._maxRetries = 5;          // 최대 5회 연속 실패 시 포기
        this._mode = null;             // 'mic' | 'system'
        this._chunkCount = 0;          // 성공한 청크 수 (디버깅용)
    }

    // 1. Mic Recording
    async startMic(interval = 3000) {
        try {
            this.interval = interval;
            this._mode = 'mic';
            this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            // 마이크 트랙 종료 감지 → 자동 재연결
            const track = this.stream.getAudioTracks()[0];
            if (track) {
                track.onended = () => {
                    console.warn('🎤 마이크 트랙 종료 감지 → 자동 재연결 시도');
                    this._tryReconnect();
                };
            }

            this.startLoop();
            console.log('🎤 Microphone recording started (Auto-Recovery Mode)');
        } catch (err) {
            console.error('Error accessing microphone:', err);
            throw err;
        }
    }

    // 2. System Audio Recording (Tab Audio)
    async startSystemAudio(interval = 3000) {
        try {
            this.interval = interval;
            this._mode = 'system';
            this.stream = await navigator.mediaDevices.getDisplayMedia({
                video: {
                    displaySurface: "browser",
                },
                audio: {
                    echoCancellation: false,
                    noiseSuppression: false,
                    autoGainControl: false,
                    sampleRate: 44100,
                    channelCount: 1
                },
                preferCurrentTab: true,
                selfBrowserSurface: "include",
                systemAudio: "include"
            });

            const audioTrack = this.stream.getAudioTracks()[0];

            if (!audioTrack) {
                this.stream.getTracks().forEach(t => t.stop());
                const msg = "오디오가 감지되지 않았습니다. '현재 탭'을 선택하고 '오디오 공유'를 켜주세요.";
                if (this.onError) this.onError(msg);
                throw new Error("No audio track detected");
            }

            // 사용자가 브라우저 UI에서 공유 중단 시
            audioTrack.onended = () => {
                console.warn("🔇 System audio track ended by user.");
                this.stop();
            };

            this.audioStream = new MediaStream([audioTrack]);

            this.startLoop();
            console.log('🔊 System audio recording started (Auto-Recovery Mode)');

        } catch (err) {
            console.error('Error capturing system audio:', err);
            throw err;
        }
    }

    // [CORE LOGIC] Smart Recording Loop (Silence Detection + Auto Recovery)
    startLoop() {
        this.isRecording = true;
        this._consecutiveErrors = 0;
        this.setupAudioAnalysis();
        this.startSmartChunk();
    }

    setupAudioAnalysis() {
        if (this.analyser) return;

        try {
            const stream = this.audioStream || this.stream;
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const source = this.audioContext.createMediaStreamSource(stream);
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            source.connect(this.analyser);

            this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
            console.log("🔊 Audio Analysis Setup Complete");
        } catch (e) {
            console.error("Audio Analysis Error:", e);
        }
    }

    startSmartChunk() {
        if (!this.isRecording) return;

        const streamToRecord = this.audioStream || this.stream;

        // 스트림 상태 검사 — 곧바로 stop하지 않고 재연결 시도
        if (!streamToRecord || streamToRecord.getAudioTracks().length === 0 || streamToRecord.getAudioTracks()[0].readyState === 'ended') {
            console.warn('⚠️ 오디오 트랙 종료 감지. 재연결 시도...');
            this._tryReconnect();
            return;
        }

        // 연속 에러 카운터 리셋 (정상 시작 성공)
        this._consecutiveErrors = 0;

        let mimeType = this.getSupportedMimeType();
        let recorder;

        try {
            recorder = new MediaRecorder(streamToRecord, mimeType ? { mimeType } : undefined);
        } catch (e) {
            try { recorder = new MediaRecorder(streamToRecord); } catch (e2) {
                console.error('MediaRecorder 생성 실패:', e2);
                this._scheduleRetry();
                return;
            }
        }

        this.currentRecorder = recorder;
        const localChunks = [];

        recorder.ondataavailable = (e) => {
            if (e.data && e.data.size > 0) localChunks.push(e.data);
        };

        recorder.onstop = () => {
            const blob = new Blob(localChunks, { type: mimeType || 'audio/webm' });
            if (blob.size > 0 && this.onDataAvailable) {
                this._chunkCount++;
                this.onDataAvailable(blob);
            }
            // 다음 청크 즉시 시작 (Gapless Sequential)
            if (this.isRecording) {
                this.startSmartChunk();
            }
        };

        // 에러 복구: MediaRecorder가 예기치 않게 중단될 때
        recorder.onerror = (e) => {
            console.error('🚨 MediaRecorder 에러:', e.error?.message || e);
            this._scheduleRetry();
        };

        try {
            recorder.start();
            this.monitorVolumeAndCut(recorder, Date.now());
        } catch (e) {
            console.error('MediaRecorder.start() 실패:', e);
            this._scheduleRetry();
        }
    }

    monitorVolumeAndCut(recorder, startTime) {
        if (!this.isRecording) return;

        // recorder가 이미 종료된 상태면 새 청크를 시작
        if (recorder.state !== 'recording') {
            console.warn('⚠️ recorder.state =', recorder.state, '→ 새 청크 시작');
            if (this.isRecording) {
                setTimeout(() => this.startSmartChunk(), 200);
            }
            return;
        }

        const duration = Date.now() - startTime;
        let isSilence = false;

        if (this.analyser) {
            this.analyser.getByteFrequencyData(this.dataArray);
            let sum = 0;
            for (let i = 0; i < this.dataArray.length; i++) {
                sum += this.dataArray[i];
            }
            const average = sum / this.dataArray.length;

            if (average < 10) isSilence = true;
        }

        // 최대 시간을 5초 → 8초로 늘림 (긴 발화 대응)
        // 최소 시간을 2초 → 3초로 늘림 (너무 잦은 잘림 방지)
        if (duration > 8000 || (duration > 3000 && isSilence)) {
            try {
                recorder.stop(); // onstop → startSmartChunk
            } catch (e) {
                console.warn('recorder.stop() 예외:', e);
                if (this.isRecording) setTimeout(() => this.startSmartChunk(), 200);
            }
        } else {
            setTimeout(() => this.monitorVolumeAndCut(recorder, startTime), 100);
        }
    }

    // 자동 재연결: 마이크 트랙이 끊겼을 때 다시 연결
    async _tryReconnect() {
        if (!this.isRecording) return;

        this._consecutiveErrors++;
        if (this._consecutiveErrors > this._maxRetries) {
            console.error(`❌ 연속 ${this._maxRetries}회 재연결 실패. 녹음 중단.`);
            this.stop();
            return;
        }

        console.log(`🔄 재연결 시도 (${this._consecutiveErrors}/${this._maxRetries})...`);

        // 기존 스트림 정리
        if (this.stream) {
            this.stream.getTracks().forEach(t => t.stop());
        }
        if (this.audioStream) {
            this.audioStream.getTracks().forEach(t => t.stop());
        }
        this.analyser = null;
        this.audioContext = null;

        try {
            if (this._mode === 'mic') {
                this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });

                const track = this.stream.getAudioTracks()[0];
                if (track) {
                    track.onended = () => {
                        console.warn('🎤 마이크 트랙 재종료 감지 → 재연결');
                        this._tryReconnect();
                    };
                }

                this.setupAudioAnalysis();
                console.log('✅ 마이크 재연결 성공. 녹음 재개.');
                this.startSmartChunk();
            } else {
                // 시스템 오디오는 사용자 인터랙션 필요 → 재연결 불가, 중단
                console.error('❌ 시스템 오디오는 자동 재연결 불가. 녹음 중단.');
                this.stop();
            }
        } catch (e) {
            console.error('재연결 실패:', e);
            // 1초 후 다시 시도
            setTimeout(() => this._tryReconnect(), 1000);
        }
    }

    // 재시도 스케줄링 (에러 후)
    _scheduleRetry() {
        this._consecutiveErrors++;
        if (this._consecutiveErrors > this._maxRetries) {
            console.error(`❌ 연속 ${this._maxRetries}회 에러. 녹음 중단.`);
            this.stop();
            return;
        }
        const delay = Math.min(500 * this._consecutiveErrors, 3000);
        console.log(`⏳ ${delay}ms 후 재시도 (${this._consecutiveErrors}/${this._maxRetries})...`);
        setTimeout(() => {
            if (this.isRecording) this.startSmartChunk();
        }, delay);
    }

    getSupportedMimeType() {
        const types = [
            'audio/webm;codecs=opus',
            'audio/webm',
            'audio/mp4',
            'audio/ogg'
        ];
        for (const type of types) {
            if (MediaRecorder.isTypeSupported(type)) return type;
        }
        return '';
    }

    stop() {
        console.log(`⏹️ Stopping recorder (총 ${this._chunkCount}개 청크 전송됨)`);
        this.isRecording = false;

        if (this.currentRecorder && this.currentRecorder.state !== 'inactive') {
            try { this.currentRecorder.stop(); } catch (e) { }
        }

        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
        }
        if (this.audioStream) {
            this.audioStream.getTracks().forEach(track => track.stop());
        }

        if (this.audioContext && this.audioContext.state !== 'closed') {
            try { this.audioContext.close(); } catch (e) { }
        }

        this.stream = null;
        this.audioStream = null;
        this.currentRecorder = null;
        this.analyser = null;
        this.audioContext = null;
    }
}
