#!/bin/bash
# Re:Boot — 전체 서버 종료
echo "🛑 Re:Boot 서버 종료 중..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:5173 | xargs kill -9 2>/dev/null
lsof -ti:5174 | xargs kill -9 2>/dev/null
echo "✅ 완료"
