"""
🎤 라즈베리파이 DS-CNN 성능 단독 테스트
STT 없이, 맥 마이크 → 라즈베리파이 소켓 직통 전송

사용법:
  python test_rpi_kws.py                    # 기본 IP 사용
  python test_rpi_kws.py 172.16.206.43      # IP 지정
  python test_rpi_kws.py 172.16.206.43 9999 # IP + 포트 지정

라즈베리파이에서 server_pi_socket.py가 실행 중이어야 합니다.
Ctrl+C로 종료합니다.
"""
import sys
import socket
import time
import numpy as np
import sounddevice as sd
import threading

# ── 설정 ──
RPI_HOST = sys.argv[1] if len(sys.argv) > 1 else '172.16.206.43'
RPI_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 9999
SAMPLE_RATE = 16000
CHUNK_DURATION_MS = 250  # 라즈베리파이 서버 프로토콜: 0.25초 단위
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)  # 4000 samples

# ── 통계 ──
stats = {
    'sent': 0,
    'quiz': 0,
    'understand': 0,
    'latency': [],
    'start_time': None,
}

def connect_rpi():
    """라즈베리파이 소켓 연결"""
    print(f'\n{"="*50}')
    print(f'  🔌 라즈베리파이 DS-CNN 성능 테스트')
    print(f'  대상: {RPI_HOST}:{RPI_PORT}')
    print(f'{"="*50}')
    print(f'\n연결 시도 중...', end=' ', flush=True)

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((RPI_HOST, RPI_PORT))
        sock.settimeout(None)
        print(f'✅ 연결 성공!')
        return sock
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        print(f'\n❌ 연결 실패: {e}')
        print(f'\n확인사항:')
        print(f'  1. 라즈베리파이에서 server_pi_socket.py가 실행 중인지')
        print(f'  2. IP 주소가 맞는지 (현재: {RPI_HOST})')
        print(f'  3. 같은 네트워크에 있는지')
        sys.exit(1)

def receive_thread(sock):
    """라즈베리파이 응답 수신 스레드"""
    buffer = b''
    while True:
        try:
            data = sock.recv(256)
            if not data:
                print('\n⚠️ 라즈베리파이 연결 끊김')
                break
            buffer += data

            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                msg = line.decode('utf-8').strip()
                now = time.time()

                if msg == 'TRIGGER_QUIZ':
                    stats['quiz'] += 1
                    print(f'\n🔥 감지: "퀴즈" [누적: {stats["quiz"]}회]')
                elif msg == 'TRIGGER_UNDERSTAND':
                    stats['understand'] += 1
                    print(f'\n🔥 감지: "이해하셨나요" [누적: {stats["understand"]}회]')
                else:
                    print(f'\n📨 수신: {msg}')

        except (ConnectionResetError, BrokenPipeError, OSError):
            print('\n⚠️ 수신 스레드 종료')
            break

def audio_callback(indata, frames, time_info, status):
    """마이크 콜백: 0.25초 오디오 → 라즈베리파이 전송"""
    global rpi_socket

    audio_chunk = indata[:, 0].astype(np.float32)
    volume = float(np.max(np.abs(audio_chunk)))

    # Float32 → Int16 (라즈베리파이 프로토콜)
    chunk_int16 = (audio_chunk * 32768.0).astype(np.int16)

    try:
        rpi_socket.sendall(chunk_int16.tobytes())
        stats['sent'] += 1

        # 상태 표시
        bar = '█' * int(volume * 50)
        elapsed = time.time() - stats['start_time']
        msg = f"  🎤 {elapsed:.0f}s | 전송: {stats['sent']} | 볼륨: {volume:.3f} |{bar}"
        print(msg.ljust(70), end='\r', flush=True)

    except (BrokenPipeError, ConnectionResetError, OSError):
        print('\n❌ 전송 실패 — 연결 끊김')

# ── 메인 실행 ──
rpi_socket = connect_rpi()

# 수신 스레드 시작
recv_t = threading.Thread(target=receive_thread, args=(rpi_socket,), daemon=True)
recv_t.start()

stats['start_time'] = time.time()

print(f'\n🎙️ 마이크 캡처 시작! (16kHz, 0.25초 청크)')
print(f'   "퀴즈" 또는 "이해하셨나요"라고 말해보세요.')
print(f'   Ctrl+C로 종료\n')

try:
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        blocksize=CHUNK_SIZE,
        callback=audio_callback,
    ):
        while True:
            time.sleep(0.1)

except KeyboardInterrupt:
    elapsed = time.time() - stats['start_time']
    print(f'\n\n{"="*50}')
    print(f'  🛑 테스트 종료')
    print(f'  총 시간: {elapsed:.1f}초')
    print(f'  전송 청크: {stats["sent"]}개 ({stats["sent"] * 0.25:.1f}초 분량)')
    print(f'  "퀴즈" 감지: {stats["quiz"]}회')
    print(f'  "이해하셨나요" 감지: {stats["understand"]}회')
    print(f'{"="*50}')

finally:
    rpi_socket.close()
