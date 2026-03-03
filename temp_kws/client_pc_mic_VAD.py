import socket
import pyaudio
import threading
import sys
import argparse
import webrtcvad

# --- 파라미터 ---
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK_DURATION_MS = 250
CHUNK = int(RATE * CHUNK_DURATION_MS / 1000)  # 4000 samples

# WebRTC VAD는 10, 20, 30ms 단위의 프레임만 처리할 수 있습니다.
VAD_FRAME_DURATION_MS = 20
VAD_FRAME_SIZE = int(RATE * VAD_FRAME_DURATION_MS / 1000) # 320 samples (640 bytes)
VAD_MODE = 2 # 0: 보통, 1: 덜 공격적, 2: 공격적 필터링, 3: 매우 공격적 (목소리만 타이트하게 잡음)

def receive_thread(sock):
    """서버(라즈베리파이)로부터 오는 트리거 알림을 비동기적으로 수신하는 스레드"""
    print("가동 준비 완료. 라즈베리파이로부터의 이벤트를 대기합니다...")
    try:
        f = sock.makefile('r', encoding='utf-8')
        while True:
            line = f.readline()
            if not line:
                break
            
            line = line.strip()
            if line.startswith("TRIGGER_"):
                keyword = line.replace("TRIGGER_", "")
                print(f"\n[🔔 서버 응답] 키워드 감지 완료! -> '{keyword}'")
                
                if keyword == 'QUIZ':
                    print(">> 퀴즈 프로세스를 실행합니다 (PC 측 로직 처리)")
                elif keyword == 'UNDERSTAND':
                    print(">> 이해도 확인 프로세스를 실행합니다 (PC 측 로직 처리)")
                
    except Exception as e:
        print(f"\n[수신 스레드 종료]: {e}")

def main():
    parser = argparse.ArgumentParser(description="PC 마이크 오디오(+VAD)를 소켓을 통해 라즈베리파이로 스트리밍합니다.")
    parser.add_argument("--ip", type=str, required=True, help="라즈베리파이의 IP 주소 (예: 192.168.0.x)")
    parser.add_argument("--port", type=int, default=9999, help="라즈베리파이 접속 포트 (기본값: 9999)")
    args = parser.parse_args()

    server_ip = args.ip
    server_port = args.port

    # 1. 소켓 연결
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        print(f"서버({server_ip}:{server_port})에 연결 중...")
        client_socket.connect((server_ip, server_port))
        print("연결 성공!")
    except Exception as e:
        print(f"❌ 접속 실패: {e}")
        sys.exit(1)

    # 2. 서버 이벤트 수신 스레드 시작
    tr = threading.Thread(target=receive_thread, args=(client_socket,), daemon=True)
    tr.start()

    # 3. VAD(Voice Activity Detection) 초기화
    vad = webrtcvad.Vad(VAD_MODE)

    # 4. 마이크 설정 (PyAudio)
    audio = pyaudio.PyAudio()
    try:
        stream = audio.open(format=FORMAT,
                            channels=CHANNELS,
                            rate=RATE,
                            input=True,
                            frames_per_buffer=CHUNK)
        
        print("\n==== 🎙️ 마이크 스트리밍 시작 (VAD 활성화 모드) ====")
        print(">> 발화를 시작해 주세요 ('퀴즈', '이해했나요')")
        print(">> 잡음이나 침묵은 전송되지 않습니다.")
        print(">> (종료하려면 Ctrl+C를 누르세요)")
        
        while True:
            # 250ms 분량의 데이터 읽기 (8000 bytes)
            data = stream.read(CHUNK, exception_on_overflow=False)
            
            # 250ms 데이터를 VAD가 인식할 수 있는 20ms 단위로 쪼개서 검사
            speech_frames_count = 0
            total_frames = CHUNK_DURATION_MS // VAD_FRAME_DURATION_MS # 250 // 20 = 12프레임 (짜투리 10ms는 무시됨)
            
            for i in range(total_frames):
                # 20ms = 320 samples = 640 bytes
                frame = data[i * 640 : (i + 1) * 640]
                if len(frame) == 640:
                    try:
                        is_speech = vad.is_speech(frame, RATE)
                        if is_speech:
                            speech_frames_count += 1
                    except Exception:
                        pass
            
            # 사람 목소리 비율 산정 (250ms 중에 사람 목소리로 추정된 기간이 몇 퍼센트인지)
            speech_ratio = speech_frames_count / total_frames
            
            # 목소리가 전체 250ms 구간 중 40% 이상 차지할 때만 서버로 전송
            if speech_ratio > 0.4:
                # print("전송 중...", end='\r', flush=True) # VAD 로거 (필요시 주석 해제)
                client_socket.sendall(data)
            else:
                # 사람 목소리가 아니거나 잡음/침묵인 경우는 서버의 버퍼를 굳이 오염시키지 않기 위해
                # 완전히 0으로 비어있는 적막한 소리 데이터(Zero padding)를 대신 보냅니다.
                # (서버쪽 슬라이딩 윈도우 폼을 유지해주기 위함)
                empty_data = bytearray(len(data))
                client_socket.sendall(empty_data)
                # print("차단됨...", end='\r', flush=True)

    except KeyboardInterrupt:
        print("\n중지 중...")
    except Exception as e:
        print(f"오류 발생: {e}")
    finally:
        print("마이크 및 소켓 접속 해제 중...")
        stream.stop_stream()
        stream.close()
        audio.terminate()
        client_socket.close()

if __name__ == "__main__":
    main()
