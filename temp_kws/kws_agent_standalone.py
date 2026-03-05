"""
KWS Local Agent (Standalone)
==============================
교수 PC에서 실행되는 단독 실행 에이전트.
브라우저(교수 대시보드)에서 ws://localhost:5555로 명령을 수신하고,
PyAudio + WebRTC VAD로 마이크를 직접 캡처하여 라즈베리파이로 전송합니다.

기존 kws_agent.py + client_pc_mic_VAD.py 기능을 하나로 통합.
PyInstaller로 .exe 패키징 시 이 파일만 사용합니다.

사용법:
  python kws_agent_standalone.py
또는:
  kws_agent_standalone.exe (패키징 후)
"""

import asyncio
import websockets
import json
import socket
import threading
import pyaudio
import webrtcvad
import sys
import os

# === WebSocket 서버 설정 ===
WS_PORT = 5555

# === 오디오 설정 (client_pc_mic_VAD.py와 동일) ===
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK_DURATION_MS = 250
CHUNK = int(RATE * CHUNK_DURATION_MS / 1000)        # 4000 samples = 8000 bytes

# VAD 설정
VAD_FRAME_DURATION_MS = 20
VAD_FRAME_SIZE = int(RATE * VAD_FRAME_DURATION_MS / 1000)  # 320 samples = 640 bytes
VAD_MODE = 2    # 2: 공격적 필터링 (확실한 목소리만 통과)
VAD_SPEECH_RATIO_THRESHOLD = 0.4   # 250ms 중 40% 이상이 음성일 때만 전송

# === 전역 상태 ===
streaming_active = False    # 오디오 스트리밍 활성화 여부
stream_thread = None        # 오디오 스트리밍 스레드
current_tcp_socket = None   # 현재 Pi TCP 소켓 (외부에서 강제 종료용)


def audio_stream_worker(rpi_ip, rpi_port):
    """
    마이크 → VAD → TCP 소켓 스트리밍 워커 (별도 스레드에서 실행)
    client_pc_mic_VAD.py의 main() 로직과 동일
    """
    global streaming_active, current_tcp_socket

    print(f"📡 라즈베리파이 연결 중... ({rpi_ip}:{rpi_port})")

    # 1. 라즈베리파이 TCP 소켓 연결
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect((rpi_ip, rpi_port))
        current_tcp_socket = client_socket  # 전역 등록 (stop시 외부 강제 종료용)
        print(f"✅ 라즈베리파이 연결 성공 ({rpi_ip}:{rpi_port})")
    except Exception as e:
        print(f"❌ 라즈베리파이 연결 실패: {e}")
        streaming_active = False
        current_tcp_socket = None
        return

    # 2. 라즈베리파이 → PC 트리거 수신 스레드
    def receive_trigger():
        try:
            f = client_socket.makefile('r', encoding='utf-8')
            while streaming_active:
                line = f.readline()
                if not line:
                    break
                line = line.strip()
                if line.startswith("TRIGGER_"):
                    keyword = line.replace("TRIGGER_", "")
                    print(f"\n🔔 키워드 감지: {keyword}")
        except Exception as e:
            if streaming_active:
                print(f"수신 스레드 종료: {e}")

    recv_thread = threading.Thread(target=receive_trigger, daemon=True)
    recv_thread.start()

    # 3. VAD 초기화
    vad = webrtcvad.Vad(VAD_MODE)

    # 4. PyAudio 마이크 스트림 시작
    audio = pyaudio.PyAudio()
    try:
        stream = audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )

        print("\n==== 🎙️ 마이크 스트리밍 시작 (VAD 활성화 모드) ====")
        print(">> 발화를 시작해 주세요 ('퀴즈', '이해했나요')")
        print(">> 잡음이나 침묵은 전송되지 않습니다.")

        chunk_count = 0
        while streaming_active:
            # 250ms 오디오 읽기
            data = stream.read(CHUNK, exception_on_overflow=False)

            # VAD: 20ms 단위로 쪼개서 음성 감지
            speech_frames_count = 0
            total_frames = CHUNK_DURATION_MS // VAD_FRAME_DURATION_MS  # 12프레임

            for i in range(total_frames):
                frame = data[i * 640: (i + 1) * 640]
                if len(frame) == 640:
                    try:
                        if vad.is_speech(frame, RATE):
                            speech_frames_count += 1
                    except Exception:
                        pass

            speech_ratio = speech_frames_count / total_frames

            try:
                if speech_ratio > VAD_SPEECH_RATIO_THRESHOLD:
                    # 음성 감지 → 실제 오디오 전송
                    client_socket.sendall(data)
                else:
                    # 침묵/잡음 → 제로 패딩 전송 (Pi 슬라이딩 윈도우 유지)
                    client_socket.sendall(bytearray(len(data)))
            except Exception as e:
                if streaming_active:
                    print(f"❌ 전송 실패: {e}")
                break

            chunk_count += 1
            if chunk_count % 40 == 0:  # 10초마다 상태 출력
                print(f"📊 스트리밍 중... ({chunk_count * 0.25:.0f}초)", end='\r')

    except Exception as e:
        print(f"오디오 오류: {e}")
    finally:
        print("\n⏹️ 마이크 스트리밍 중지")
        try:
            stream.stop_stream()
            stream.close()
        except Exception:
            pass
        audio.terminate()
        try:
            client_socket.close()
        except Exception:
            pass
        current_tcp_socket = None  # 전역 소켓 해제
        print("📡 라즈베리파이 TCP 연결 해제")


def start_streaming(rpi_ip, rpi_port):
    """오디오 스트리밍 시작"""
    global streaming_active, stream_thread

    # 이미 실행 중이면 먼저 중지
    stop_streaming()

    streaming_active = True
    stream_thread = threading.Thread(
        target=audio_stream_worker,
        args=(rpi_ip, rpi_port),
        daemon=True
    )
    stream_thread.start()
    return True


def stop_streaming():
    """오디오 스트리밍 중지"""
    global streaming_active, stream_thread, current_tcp_socket

    if not streaming_active:
        return False

    streaming_active = False

    # TCP 소켓을 먼저 강제 종료 → stream.read() 바로 해제
    if current_tcp_socket:
        try:
            current_tcp_socket.shutdown(socket.SHUT_RDWR)
            current_tcp_socket.close()
        except Exception:
            pass
        current_tcp_socket = None

    if stream_thread and stream_thread.is_alive():
        stream_thread.join(timeout=3)
    stream_thread = None
    return True


def get_status():
    """현재 스트리밍 상태 반환"""
    return {
        "running": streaming_active and stream_thread is not None and stream_thread.is_alive()
    }


async def handler(websocket):
    """WebSocket 메시지 핸들러"""
    client_addr = websocket.remote_address
    print(f"🔌 대시보드 연결: {client_addr}")

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                action = data.get('action', '')

                if action == 'start':
                    rpi_ip = data.get('ip', '')
                    rpi_port = data.get('port', 9999)

                    if not rpi_ip:
                        await websocket.send(json.dumps({
                            "status": "error",
                            "message": "IP 주소가 필요합니다."
                        }))
                        continue

                    print(f"\n▶️  START 명령 수신 (IP: {rpi_ip}:{rpi_port})")
                    success = start_streaming(rpi_ip, rpi_port)
                    await websocket.send(json.dumps({
                        "status": "started" if success else "error",
                        "message": "스트리밍 시작" if success else "시작 실패"
                    }))

                elif action == 'stop':
                    print(f"\n⏹️  STOP 명령 수신")
                    success = stop_streaming()
                    await websocket.send(json.dumps({
                        "status": "stopped" if success else "not_running",
                        "message": "스트리밍 중지" if success else "실행 중이 아님"
                    }))

                elif action == 'status':
                    status = get_status()
                    await websocket.send(json.dumps({
                        "status": "ok",
                        **status
                    }))

                elif action == 'shutdown':
                    print(f"\n🛑  SHUTDOWN 명령 수신: 에이전트를 종료합니다.")
                    await websocket.send(json.dumps({
                        "status": "shutdown",
                        "message": "에이전트 종료 중..."
                    }))
                    stop_streaming()
                    # asyncio.get_running_loop().stop() 대신 sys.exit()을 사용하여 확실히 종료
                    os._exit(0)

                else:
                    await websocket.send(json.dumps({
                        "status": "error",
                        "message": f"알 수 없는 명령: {action}"
                    }))

            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    "status": "error",
                    "message": "잘못된 JSON"
                }))

    except websockets.exceptions.ConnectionClosed:
        print(f"🔌 대시보드 연결 해제: {client_addr}")
        # 브라우저가 끊기면 스트리밍도 중지
        if streaming_active:
            print("대시보드 연결 해제 — 스트리밍 유지 중 (세션 종료 시 자동 중지)")


async def main():
    print("=" * 52)
    print(f"🟢 KWS Local Agent (Standalone) 시작")
    print(f"   WebSocket: ws://localhost:{WS_PORT}")
    print(f"   오디오: PyAudio + WebRTC VAD (MODE {VAD_MODE})")
    print("=" * 52)
    print("교수 대시보드에서 라이브 세션을 시작하면")
    print("자동으로 마이크 스트리밍이 시작됩니다.")
    print("이 창을 닫지 마세요. (종료: Ctrl+C)\n")

    async with websockets.serve(handler, "localhost", WS_PORT):
        while True:
            await asyncio.sleep(1)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 종료 중...")
        stop_streaming()
        print("Agent가 종료되었습니다.")
