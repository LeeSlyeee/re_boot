"""
오디오 중계 서버 (Audio Relay Server)
======================================
브라우저(교수 대시보드)에서 WebSocket으로 수신한 마이크 오디오를
라즈베리파이의 TCP 소켓(9999)으로 중계하고,
라즈베리파이의 KWS 트리거 응답을 브라우저로 반환합니다.

브라우저 → WebSocket(:8001) → 이 서버 → TCP(:9999) → Raspberry Pi
                                                      ↓
브라우저 ← WebSocket ← 이 서버 ← TCP ← TRIGGER_QUIZ / TRIGGER_UNDERSTAND

사용법:
  pip install websockets
  python audio_relay.py

오디오 스펙 (client_pc_mic_VAD.py와 동일):
  - 샘플링 레이트: 16,000 Hz
  - 채널: 1 (모노)
  - 포맷: Int16 Little Endian
  - 청크 크기: 250ms = 4,000 samples = 8,000 bytes
"""

import asyncio
import websockets
import json
import socket
import threading
import sys

# === 설정 ===
WS_HOST = '0.0.0.0'
WS_PORT = 8001
AUDIO_CHUNK_BYTES = 8000  # 250ms @ 16kHz, Int16 모노 = 4000 samples * 2 bytes


async def handle_client(websocket):
    """
    브라우저 클라이언트 1개의 WebSocket 연결을 처리합니다.
    
    프로토콜:
    1. 브라우저가 JSON으로 연결 정보를 전송:
       {"action": "connect", "ip": "라즈베리파이IP", "port": 9999}
    2. 서버가 라즈베리파이에 TCP 연결 시도
    3. 성공 시 {"status": "connected"} 응답
    4. 이후 브라우저가 바이너리(PCM 오디오)를 전송 → TCP로 전달
    5. 라즈베리파이의 텍스트 응답(TRIGGER_*) → WebSocket으로 전달
    """
    client_addr = websocket.remote_address
    print(f"🔌 브라우저 연결: {client_addr}")
    
    tcp_socket = None
    tcp_reader_task = None
    
    try:
        # 1단계: 연결 정보 수신
        init_msg = await asyncio.wait_for(websocket.recv(), timeout=10)
        init_data = json.loads(init_msg)
        
        if init_data.get('action') != 'connect':
            await websocket.send(json.dumps({
                "status": "error",
                "message": "첫 메시지는 connect 액션이어야 합니다."
            }))
            return
        
        rpi_ip = init_data.get('ip', '')
        rpi_port = int(init_data.get('port', 9999))
        
        if not rpi_ip:
            await websocket.send(json.dumps({
                "status": "error",
                "message": "라즈베리파이 IP가 필요합니다."
            }))
            return
        
        # 2단계: 라즈베리파이에 TCP 연결
        print(f"📡 라즈베리파이 연결 시도: {rpi_ip}:{rpi_port}")
        tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_socket.settimeout(5.0)  # 연결 타임아웃 5초
        
        try:
            tcp_socket.connect((rpi_ip, rpi_port))
            tcp_socket.settimeout(0.1)  # 이후에는 논블로킹에 가깝게
            print(f"✅ 라즈베리파이 연결 성공: {rpi_ip}:{rpi_port}")
        except Exception as e:
            print(f"❌ 라즈베리파이 연결 실패: {e}")
            await websocket.send(json.dumps({
                "status": "error",
                "message": f"라즈베리파이 연결 실패: {str(e)}"
            }))
            return
        
        await websocket.send(json.dumps({
            "status": "connected",
            "message": f"라즈베리파이 연결 성공 ({rpi_ip}:{rpi_port})"
        }))
        
        # 3단계: 라즈베리파이 → 브라우저 응답 전달 (별도 태스크)
        stop_event = asyncio.Event()
        
        async def read_tcp_responses():
            """라즈베리파이에서 보내는 TRIGGER 응답을 읽어 WebSocket으로 전달"""
            loop = asyncio.get_event_loop()
            while not stop_event.is_set():
                try:
                    # TCP에서 논블로킹으로 읽기
                    data = await loop.run_in_executor(None, lambda: tcp_socket.recv(1024))
                    if not data:
                        break
                    text = data.decode('utf-8', errors='ignore').strip()
                    if text:
                        for line in text.split('\n'):
                            line = line.strip()
                            if line.startswith('TRIGGER_'):
                                keyword = line.replace('TRIGGER_', '')
                                print(f"🔔 KWS 트리거 감지: {keyword}")
                                try:
                                    await websocket.send(json.dumps({
                                        "type": "trigger",
                                        "keyword": keyword
                                    }))
                                except:
                                    break
                except socket.timeout:
                    await asyncio.sleep(0.05)
                except Exception:
                    break
        
        tcp_reader_task = asyncio.create_task(read_tcp_responses())
        
        # 4단계: 브라우저 → 라즈베리파이 오디오 전달 (메인 루프)
        chunk_count = 0
        async for message in websocket:
            if isinstance(message, bytes):
                # 바이너리 메시지 = PCM 오디오 데이터
                try:
                    tcp_socket.sendall(message)
                    chunk_count += 1
                    if chunk_count % 40 == 0:  # 10초마다 로그
                        print(f"📊 오디오 중계 중... ({chunk_count} 청크, {chunk_count * 0.25:.0f}초)")
                except Exception as e:
                    print(f"❌ TCP 전송 실패: {e}")
                    break
            elif isinstance(message, str):
                # 텍스트 메시지 = 제어 명령
                try:
                    cmd = json.loads(message)
                    if cmd.get('action') == 'stop':
                        print("🛑 브라우저에서 중지 요청")
                        break
                except json.JSONDecodeError:
                    pass
    
    except websockets.exceptions.ConnectionClosed:
        print(f"🔌 브라우저 연결 해제: {client_addr}")
    except asyncio.TimeoutError:
        print(f"⏰ 연결 정보 수신 타임아웃: {client_addr}")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
    finally:
        # 정리
        if tcp_reader_task:
            tcp_reader_task.cancel()
            try:
                await tcp_reader_task
            except asyncio.CancelledError:
                pass
        
        if tcp_socket:
            try:
                tcp_socket.close()
                print("📡 라즈베리파이 TCP 연결 해제")
            except:
                pass
        
        print(f"🔌 세션 종료: {client_addr}\n")


async def main():
    print("=" * 55)
    print(f"🟢 오디오 중계 서버 시작 (Audio Relay)")
    print(f"   WebSocket: ws://0.0.0.0:{WS_PORT}")
    print(f"   오디오 포맷: 16kHz, Int16, 모노, 250ms 청크")
    print("=" * 55)
    print("교수 대시보드에서 라즈베리파이 연결 시")
    print("브라우저 → 이 서버 → 라즈베리파이로 오디오가 중계됩니다.")
    print("(종료: Ctrl+C)\n")
    
    async with websockets.serve(handle_client, WS_HOST, WS_PORT):
        await asyncio.Future()  # 무한 대기


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 중계 서버 종료")
