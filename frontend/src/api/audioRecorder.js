export class AudioRecorder {
    constructor(onDataAvailable) {
      this.onDataAvailable = onDataAvailable; 
      this.stream = null;
      this.audioStream = null;
      this.isRecording = false;
      this.interval = 3000;
      this.currentRecorder = null;
    }
  
    // 1. Mic Recording
    async startMic(interval = 3000) {
      try {
        this.interval = interval;
        this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        this.startLoop();
        console.log('Microphone recording started (Recursive Mode)');
      } catch (err) {
        console.error('Error accessing microphone:', err);
        throw err;
      }
    }

    // 2. System Audio Recording (Tab Audio)
    async startSystemAudio(interval = 3000) {
        try {
            this.interval = interval;
            // [System Audio Constraints]
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
                preferCurrentTab: true, // Chrome/Edge
                selfBrowserSurface: "include", // Standard
                systemAudio: "include" 
            });

            const audioTrack = this.stream.getAudioTracks()[0];
            
            if (!audioTrack) {
                this.stream.getTracks().forEach(t => t.stop());
                alert("❌ 중요: 오디오가 감지되지 않았습니다!\n\n반드시 '현재 탭'을 선택하고 '오디오 공유'를 켜주세요.");
                throw new Error("No audio track detected");
            }
            
            // Listen for user stopping sharing via browser UI
            audioTrack.onended = () => {
                console.log("System audio track ended by user.");
                this.stop();
            };

            // Independent stream
            this.audioStream = new MediaStream([audioTrack]);
            
            this.startLoop();
            console.log('System audio recording started (Recursive Mode)');

        } catch (err) {
            console.error('Error capturing system audio:', err);
            throw err;
        }
    }

    // [CORE LOGIC] Smart Recording Loop (Silence Detection)
    // 1. Monitor Volume
    // 2. If duration > 2s AND Silence Detected -> Cut & Send
    // 3. If duration > 5s -> Force Cut & Send
    startLoop() {
        this.isRecording = true;
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
        if (!streamToRecord || streamToRecord.getAudioTracks().length === 0 || streamToRecord.getAudioTracks()[0].readyState === 'ended') {
            this.stop();
            return;
        }

        let mimeType = this.getSupportedMimeType();
        let recorder;
        
        try {
           recorder = new MediaRecorder(streamToRecord, mimeType ? { mimeType } : undefined);
        } catch (e) {
            try { recorder = new MediaRecorder(streamToRecord); } catch (e2) { return; }
        }

        this.currentRecorder = recorder;
        const localChunks = [];

        recorder.ondataavailable = (e) => {
            if (e.data && e.data.size > 0) localChunks.push(e.data);
        };

        recorder.onstop = () => {
             const blob = new Blob(localChunks, { type: mimeType || 'audio/webm' });
             if (blob.size > 0 && this.onDataAvailable) {
                 this.onDataAvailable(blob);
             }
             // Smart Loop: Start NEXT chunk immediately after previous stops (Gapless Sequential)
             if (this.isRecording) {
                 this.startSmartChunk();
             }
        };
        
        recorder.start();
        this.monitorVolumeAndCut(recorder, Date.now());
    }

    monitorVolumeAndCut(recorder, startTime) {
        if (!this.isRecording || recorder.state !== 'recording') return;

        const duration = Date.now() - startTime;
        let isSilence = false;

        if (this.analyser) {
            this.analyser.getByteFrequencyData(this.dataArray);
            // Calculate average volume
            let sum = 0;
            for (let i = 0; i < this.dataArray.length; i++) {
                sum += this.dataArray[i];
            }
            const average = sum / this.dataArray.length;
            
            // Threshold: < 10 (out of 255) is roughly silence
            if (average < 10) isSilence = true;
        }

        // Logic:
        // 1. Min Duration: 2000ms (Don't cut too often)
        // 2. Max Duration: 5000ms (Must cut to keep latency low)
        // 3. Cut Condition: Min Duration passed AND Silence Detected
        
        if (duration > 5000 || (duration > 2000 && isSilence)) {
            // Cut!
            recorder.stop(); // This triggers onstop -> startSmartChunk
        } else {
            // Check again in 100ms
            setTimeout(() => this.monitorVolumeAndCut(recorder, startTime), 100);
        }
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
      console.log('Stopping recorder...');
      this.isRecording = false; 
      
      // Stop current recorder if active
      if (this.currentRecorder && this.currentRecorder.state !== 'inactive') {
        try { this.currentRecorder.stop(); } catch(e) {}
      }
      
      // Stop all actual tracks
      if (this.stream) {
          this.stream.getTracks().forEach(track => track.stop());
      }
      if (this.audioStream) {
          this.audioStream.getTracks().forEach(track => track.stop());
      }
      
      this.stream = null;
      this.audioStream = null;
      this.currentRecorder = null;
    }
}
