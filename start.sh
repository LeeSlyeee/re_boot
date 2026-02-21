#!/bin/bash
# ============================================================
# Re:Boot 프로젝트 — 원클릭 실행 스크립트
# 사용법: ./start.sh        (전체 시작)
#         ./start.sh stop   (전체 종료)
# ============================================================

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

stop_servers() {
    echo "🛑 서버 종료 중..."
    lsof -ti:8000 | xargs kill -9 2>/dev/null
    lsof -ti:5173 | xargs kill -9 2>/dev/null
    lsof -ti:5174 | xargs kill -9 2>/dev/null
    echo "✅ 완료"
}

if [ "$1" = "stop" ]; then
    stop_servers
    exit 0
fi

echo "🚀 Re:Boot 프로젝트 서버 시작"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 기존 프로세스 정리
stop_servers
sleep 1

# 가상환경 활성화
source "$PROJECT_ROOT/venv/bin/activate"
echo "🐍 가상환경 활성화: $(which python)"

# 1. Backend (Django)
echo ""
echo "⚙️  [1/3] Backend 서버 (port 8000)..."
cd "$PROJECT_ROOT/backend"
nohup python manage.py runserver 0.0.0.0:8000 > /tmp/reboot_backend.log 2>&1 &
sleep 2
if lsof -i :8000 > /dev/null 2>&1; then
    echo "  ✅ http://localhost:8000"
else
    echo "  ❌ 실패 → tail /tmp/reboot_backend.log"
fi

# 2. Frontend (Student)
echo ""
echo "🎓 [2/3] 학생 Frontend (port 5173)..."
cd "$PROJECT_ROOT/frontend"
FIFO1=/tmp/reboot_frontend_fifo
rm -f $FIFO1 && mkfifo $FIFO1
(cat $FIFO1 | npx vite --port 5173 > /tmp/reboot_frontend.log 2>&1 &)
sleep 2
if lsof -i :5173 > /dev/null 2>&1; then
    echo "  ✅ http://localhost:5173"
else
    echo "  ❌ 실패 → tail /tmp/reboot_frontend.log"
fi

# 3. Professor Dashboard
echo ""
echo "👨‍🏫 [3/3] 교수자 Dashboard (port 5174)..."
cd "$PROJECT_ROOT/Professor_dashboard"
FIFO2=/tmp/reboot_professor_fifo
rm -f $FIFO2 && mkfifo $FIFO2
(cat $FIFO2 | npx vite --port 5174 > /tmp/reboot_professor.log 2>&1 &)
sleep 2
if lsof -i :5174 > /dev/null 2>&1; then
    echo "  ✅ http://localhost:5174"
else
    echo "  ❌ 실패 → tail /tmp/reboot_professor.log"
fi

# 결과
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🟢 서버 현황:"
lsof -i :8000 -i :5173 -i :5174 -sTCP:LISTEN 2>/dev/null | grep LISTEN | awk '{print "  "$1" → "$9}'
echo ""
echo "  종료: ./start.sh stop"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
