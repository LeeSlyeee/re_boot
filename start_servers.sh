#!/bin/bash
# ============================================================
# Re:Boot 서버 일괄 시작 스크립트 (Mac용)
# 사용법: bash start_servers.sh
# ============================================================

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_DIR="$ROOT_DIR/.pids"
LOG_DIR="$ROOT_DIR/.logs"

# ── 기존 프로세스 정리 ──
echo "🧹 기존 프로세스 정리..."
bash "$ROOT_DIR/stop_servers.sh" 2>/dev/null || true

mkdir -p "$PID_DIR" "$LOG_DIR"

# ── 서비스 시작 함수 ──
start_service() {
    local name="$1"
    local dir="$2"
    local cmd="$3"
    local pid_file="$PID_DIR/${name}.pid"

    # 이미 실행 중이면 스킵
    if [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
        echo "⚠️  $name 이미 실행 중 (PID $(cat "$pid_file"))"
        return
    fi

    echo "🚀 $name 시작 중..."
    # 서브쉘에서 cd 후 실행 → disown으로 터미널 종료 영향 차단
    (cd "$dir" && exec bash -c "$cmd") > "$LOG_DIR/${name}.log" 2>&1 &
    local pid=$!
    disown $pid
    echo "$pid" > "$pid_file"
    echo "✅ $name 시작됨 (PID $pid) — 로그: .logs/${name}.log"
}

# ── 1. 백엔드 (Django, port 8000) ──
start_service "backend" "$ROOT_DIR/backend" \
    "source venv/bin/activate && exec python manage.py runserver 127.0.0.1:8000"

# ── 2. 학생용 프론트엔드 (Vite, port 5173) ──
start_service "frontend" "$ROOT_DIR/frontend" \
    "exec npx vite --host 127.0.0.1 --port 5173"

# ── 3. 교수용 대시보드 (Vite, port 5174) ──
start_service "dashboard" "$ROOT_DIR/Professor_dashboard" \
    "exec npx vite --host 127.0.0.1 --port 5174"

# ── 기동 확인 (최대 10초 대기) ──
echo ""
echo "⏳ 서버 기동 확인 중..."
sleep 3

check_port() {
    local name="$1"
    local port="$2"
    for i in $(seq 1 7); do
        if curl -s -o /dev/null -m 2 "http://127.0.0.1:${port}"; then
            echo "✅ $name → http://127.0.0.1:${port}  정상"
            return 0
        fi
        sleep 1
    done
    echo "❌ $name → http://127.0.0.1:${port}  응답 없음 (로그: .logs/${name}.log)"
    return 1
}

check_port "백엔드"       8000
check_port "학생 프론트"   5173
check_port "교수 대시보드" 5174

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  서버 중지: bash stop_servers.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
