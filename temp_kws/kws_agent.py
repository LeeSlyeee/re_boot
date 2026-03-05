"""
KWS Local WebSocket Agent
==========================
교수 PC에서 상시 실행되는 경량 WebSocket 서버입니다.
교수 대시보드(브라우저)에서 ws://localhost:5555로 명령을 수신하여
client_pc_mic_VAD.py 프로세스를 자동으로 실행/종료합니다.

사용법:
  conda activate kws
  python kws_agent.py

또는:
  start_kws_agent.bat 더블클릭
"""

import asyncio
import websockets
import json
import subprocess
import sys
import os

# === 설정 ===
WS_PORT = 5555
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SCRIPT = os.path.join(SCRIPT_DIR, 'client_pc_mic_VAD.py')

# 현재 실행 중인 KWS 마이크 클라이언트 프로세스
kws_process = None


def start_kws_client(ip, port=9999):
    """client_pc_mic_VAD.py를 subprocess로 실행"""
    global kws_process

    # 이미 실행 중이면 먼저 종료
    stop_kws_client()

    try:
        # 현재 Python 인터프리터로 실행 (conda 환경 상속)
        cmd = [sys.executable, CLIENT_SCRIPT, '--ip', str(ip), '--port', str(port)]

        # 새 콘솔 창에서 실행 (Windows 전용 플래그)
        creation_flags = subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0

        kws_process = subprocess.Popen(
            cmd,
            creationflags=creation_flags,
            cwd=SCRIPT_DIR
        )
        print(f"✅ KWS 클라이언트 시작 (PID: {kws_process.pid}, IP: {ip}:{port})")
        return True
    except Exception as e:
        print(f"❌ KWS 클라이언트 실행 실패: {e}")
        kws_process = None
        return False


def stop_kws_client():
    """실행 중인 client_pc_mic_VAD.py 프로세스를 종료"""
    global kws_process

    if kws_process is None:
        return False

    try:
        if kws_process.poll() is None:  # 아직 살아있으면
            kws_process.terminate()
            try:
                kws_process.wait(timeout=3)  # 최대 3초 대기
            except subprocess.TimeoutExpired:
                kws_process.kill()  # 강제 종료
            print(f"🛑 KWS 클라이언트 종료 (PID: {kws_process.pid})")
        kws_process = None
        return True
    except Exception as e:
        print(f"⚠️ KWS 클라이언트 종료 중 오류: {e}")
        kws_process = None
        return False


def get_status():
    """현재 KWS 클라이언트 실행 상태 반환"""
    if kws_process is None:
        return {"running": False, "pid": None}

    is_running = kws_process.poll() is None
    if not is_running:
        return {"running": False, "pid": None}

    return {"running": True, "pid": kws_process.pid}


async def handler(websocket):
    """WebSocket 메시지 핸들러"""
    client_addr = websocket.remote_address
    print(f"🔌 클라이언트 연결: {client_addr}")

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                action = data.get('action', '')

                if action == 'start':
                    # 라즈베리파이 IP와 포트를 받아 마이크 클라이언트 실행
                    ip = data.get('ip', '')
                    port = data.get('port', 9999)

                    if not ip:
                        await websocket.send(json.dumps({
                            "status": "error",
                            "message": "IP 주소가 필요합니다."
                        }))
                        continue

                    success = start_kws_client(ip, port)
                    await websocket.send(json.dumps({
                        "status": "started" if success else "error",
                        "message": f"KWS 클라이언트 {'시작' if success else '실행 실패'}"
                    }))

                elif action == 'stop':
                    # 실행 중인 마이크 클라이언트 종료
                    success = stop_kws_client()
                    await websocket.send(json.dumps({
                        "status": "stopped" if success else "not_running",
                        "message": f"KWS 클라이언트 {'종료' if success else '이미 중지 상태'}"
                    }))

                elif action == 'status':
                    # 현재 상태 조회
                    status = get_status()
                    await websocket.send(json.dumps({
                        "status": "ok",
                        **status
                    }))

                else:
                    await websocket.send(json.dumps({
                        "status": "error",
                        "message": f"알 수 없는 명령: {action}"
                    }))

            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    "status": "error",
                    "message": "잘못된 JSON 형식"
                }))

    except websockets.exceptions.ConnectionClosed:
        print(f"🔌 클라이언트 연결 해제: {client_addr}")


async def main():
    """메인 WebSocket 서버 실행"""
    print("=" * 50)
    print(f"🟢 KWS Local Agent 시작")
    print(f"   WebSocket: ws://localhost:{WS_PORT}")
    print(f"   클라이언트 스크립트: {CLIENT_SCRIPT}")
    print("=" * 50)
    print("교수 대시보드에서 라이브 세션을 시작하면")
    print("자동으로 마이크 클라이언트가 실행됩니다.")
    print("이 창을 닫지 마세요. (종료: Ctrl+C)\n")

    async with websockets.serve(handler, "localhost", WS_PORT):
        await asyncio.Future()  # 무한 대기


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Agent 종료 중...")
        stop_kws_client()
        print("Agent가 종료되었습니다.")
