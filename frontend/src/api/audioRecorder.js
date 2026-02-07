export class AudioRecorder {
    constructor(onDataAvailable) {
      this.mediaRecorder = null;
      this.chunks = [];
      this.onDataAvailable = onDataAvailable; 
      this.stream = null;
    }
  
    // 1. Mic Recording (Offline Mode)
    async startMic(timeslice = 3000) {
      try {
        this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        this.startRecording(this.stream, timeslice);
        console.log('Microphone recording started');
      } catch (err) {
        console.error('Error accessing microphone:', err);
        throw err;
      }
    }

    // 2. Tab/System Audio Capture (Online Mode)
    async startSystemAudio(timeslice = 3000) {
        try {
            // Request Display Media (Screen Share) with Audio
            this.stream = await navigator.mediaDevices.getDisplayMedia({
                video: true, // Video is required to get audio in getDisplayMedia
                audio: {
                    echoCancellation: false,
                    noiseSuppression: false,
                    sampleRate: 44100
                }
            });

            // We only need the audio track
            const audioTrack = this.stream.getAudioTracks()[0];
            
            if (!audioTrack) {
                alert("오디오 공유가 선택되지 않았습니다. '탭 오디오 공유'를 체크해주세요.");
                this.stop();
                return;
            }

            // Create a new stream with just the audio to save bandwidth/processing
            const audioStream = new MediaStream([audioTrack]);
            this.startRecording(audioStream, timeslice);
            console.log('System audio recording started');

        } catch (err) {
            console.error('Error capturing system audio:', err);
            throw err;
        }
    }

    // Shared Recorder Logic
    startRecording(stream, timeslice) {
        this.stream = stream;
        this.timeslice = timeslice;
        this.isRecording = true;
        this.recordNextChunk();
    }

    recordNextChunk() {
        if (!this.isRecording) return;

        this.mediaRecorder = new MediaRecorder(this.stream, { mimeType: 'audio/webm' });

        this.mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0 && this.onDataAvailable) {
                this.onDataAvailable(event.data);
            }
        };

        this.mediaRecorder.onstop = () => {
            if (this.isRecording) {
                // Restart immediately for next chunk
                this.recordNextChunk();
            }
        };

        this.mediaRecorder.start();
        
        // Stop after timeslice (triggering onstop -> recordNextChunk)
        this.timer = setTimeout(() => {
            if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
                this.mediaRecorder.stop();
            }
        }, this.timeslice);
    }
  
    stop() {
      this.isRecording = false;
      if (this.timer) clearTimeout(this.timer);
      
      if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
        this.mediaRecorder.stop();
      }
      if (this.stream) {
          this.stream.getTracks().forEach(track => track.stop());
      }
      console.log('Recording stopped');
    }
  }
