#!/bin/bash
# ============================================================
# Re:Boot 서버 일괄 중지 스크립트
# 사용법: bash stop_servers.sh
# ============================================================

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_DIR="$ROOT_DIR/.pids"

stop_service() {
    local name="$1"
    local pid_file="$PID_DIR/${name}.pid"

    if [ ! -f "$pid_file" ]; then
        return
    fi

    local pid
    pid=$(cat "$pid_file")

    if kill -0 "$pid" 2>/dev/null; then
        # 자식 프로세스까지 모두 종료
        pkill -P "$pid" 2>/dev/null
        kill "$pid" 2>/dev/null
        sleep 1
        # 그래도 살아있으면 강제 종료
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null
        fi
        echo "🛑 $name 종료됨 (PID $pid)"
    fi

    rm -f "$pid_file"
}

echo "🛑 서버 중지 중..."
stop_service "backend"
stop_service "frontend"
stop_service "dashboard"

# 혹시 남아있는 포트 점유 프로세스 정리
for port in 8000 5173 5174; do
    pid=$(lsof -ti TCP:$port -sTCP:LISTEN 2>/dev/null)
    if [ -n "$pid" ]; then
        kill -9 $pid 2>/dev/null
        echo "🧹 포트 $port 점유 프로세스 강제 정리 (PID $pid)"
    fi
done

rm -rf "$PID_DIR"
echo "✅ 모든 서버 중지 완료"
